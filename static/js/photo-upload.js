/**
 * BAKY Photo Upload — client-side compression and background upload with retry.
 *
 * Uses Alpine.js for reactive state and Canvas API for image compression.
 * Designed for mobile-first use on iOS Safari and Android Chrome.
 */

const MAX_DIMENSION = 2048;
const TARGET_SIZE_KB = 1800; // Target < 2MB after compression
const INITIAL_QUALITY = 0.85;
const MIN_QUALITY = 0.5;
const MAX_RETRIES = 3;
const RETRY_BASE_MS = 1000;

/**
 * Compress an image file using Canvas API.
 * Resizes to MAX_DIMENSION and reduces JPEG quality until under TARGET_SIZE_KB.
 *
 * @param {File} file - The image file to compress
 * @returns {Promise<Blob>} - The compressed JPEG blob
 */
async function compressImage(file) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      let { width, height } = img;

      // Scale down if larger than MAX_DIMENSION
      if (width > MAX_DIMENSION || height > MAX_DIMENSION) {
        const ratio = Math.min(MAX_DIMENSION / width, MAX_DIMENSION / height);
        width = Math.round(width * ratio);
        height = Math.round(height * ratio);
      }

      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0, width, height);

      // Try progressively lower quality until under target size
      let quality = INITIAL_QUALITY;
      const tryCompress = () => {
        canvas.toBlob(
          (blob) => {
            if (!blob) {
              reject(new Error("Komprimierung fehlgeschlagen"));
              return;
            }
            if (blob.size > TARGET_SIZE_KB * 1024 && quality > MIN_QUALITY) {
              quality -= 0.1;
              tryCompress();
            } else {
              resolve(blob);
            }
          },
          "image/jpeg",
          quality
        );
      };
      tryCompress();
    };
    img.onerror = () => reject(new Error("Bild konnte nicht geladen werden"));
    img.src = URL.createObjectURL(file);
  });
}

/**
 * Upload a compressed photo with retry and exponential backoff.
 *
 * @param {string} url - The upload endpoint URL
 * @param {FormData} formData - Form data including the file
 * @param {Function} onProgress - Progress callback (0-100)
 * @param {string} csrfToken - CSRF token
 * @returns {Promise<string>} - The response HTML
 */
async function uploadWithRetry(url, formData, onProgress, csrfToken) {
  let lastError;

  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    try {
      const response = await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", url, true);
        xhr.setRequestHeader("X-CSRFToken", csrfToken);
        xhr.setRequestHeader("HX-Request", "true");

        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            onProgress(Math.round((e.loaded / e.total) * 100));
          }
        };

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(xhr.responseText);
          } else {
            reject(new Error(`Upload fehlgeschlagen (${xhr.status})`));
          }
        };

        xhr.onerror = () => reject(new Error("Netzwerkfehler"));
        xhr.send(formData);
      });

      return response;
    } catch (err) {
      lastError = err;
      if (attempt < MAX_RETRIES - 1) {
        const delay = RETRY_BASE_MS * Math.pow(2, attempt);
        await new Promise((r) => setTimeout(r, delay));
      }
    }
  }

  throw lastError;
}

/**
 * Alpine.js component for photo upload per section (item or general).
 *
 * Usage:
 *   x-data="photoUploader('/inspector/5/photos/upload/', 'item_id', '42')"
 */
function photoUploader(uploadUrl, itemIdField, itemIdValue) {
  return {
    uploads: [], // {id, status: 'compressing'|'uploading'|'success'|'failed', progress, preview, error}
    nextId: 0,

    triggerCapture() {
      this.$refs.fileInput.click();
    },

    async handleFiles(event) {
      const files = Array.from(event.target.files);
      for (const file of files) {
        this.processFile(file);
      }
      // Reset input so the same file can be re-selected
      event.target.value = "";
    },

    async processFile(file) {
      const id = this.nextId++;
      const preview = URL.createObjectURL(file);
      this.uploads.push({
        id,
        status: "compressing",
        progress: 0,
        preview,
        error: null,
      });

      try {
        // Compress
        const compressed = await compressImage(file);
        const upload = this.uploads.find((u) => u.id === id);
        if (!upload) return;
        upload.status = "uploading";

        // Build form data
        const formData = new FormData();
        formData.append("file", compressed, file.name.replace(/\.[^.]+$/, ".jpg"));
        if (itemIdField && itemIdValue) {
          formData.append(itemIdField, itemIdValue);
        }

        const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]")?.value
          || document.querySelector('body')?.getAttribute('hx-headers')?.match(/"X-CSRFToken":\s*"([^"]+)"/)?.[1]
          || "";

        if (!csrfToken) {
          throw new Error("CSRF-Token nicht gefunden. Bitte Seite neu laden.");
        }

        // Upload with retry
        const html = await uploadWithRetry(
          uploadUrl,
          formData,
          (p) => {
            const u = this.uploads.find((u) => u.id === id);
            if (u) u.progress = p;
          },
          csrfToken
        );

        // Success — insert the returned HTML into the photo grid
        const u2 = this.uploads.find((u) => u.id === id);
        if (u2) u2.status = "success";

        // Append photo to grid
        const grid = this.$refs.photoGrid;
        if (grid && html) {
          const temp = document.createElement("div");
          temp.innerHTML = html;
          // Insert before the add button
          const addBtn = grid.querySelector("[data-photo-add]");
          if (addBtn) {
            grid.insertBefore(temp.firstElementChild, addBtn);
          } else {
            grid.insertAdjacentHTML("beforeend", html);
          }
          // Re-process HTMX content
          if (window.htmx) {
            htmx.process(grid);
          }
        }

        // Remove upload indicator after a short delay
        setTimeout(() => {
          this.uploads = this.uploads.filter((u) => u.id !== id);
          URL.revokeObjectURL(preview);
        }, 1500);
      } catch (err) {
        const u = this.uploads.find((u) => u.id === id);
        if (u) {
          u.status = "failed";
          u.error = err.message;
        }
      }
    },

    dismissUpload(id) {
      const upload = this.uploads.find((u) => u.id === id);
      if (upload?.preview) URL.revokeObjectURL(upload.preview);
      this.uploads = this.uploads.filter((u) => u.id !== id);
    },
  };
}

// Make available globally for Alpine.js
window.photoUploader = photoUploader;
window.compressImage = compressImage;
