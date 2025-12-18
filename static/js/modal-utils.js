/**
 * Modal Utilities - Genbrugelige modal-dialogs
 *
 * Brug: confirmWithInput() til sletning/destruktive handlinger
 *       alertModal() til beskeder
 */

(function(window) {
    'use strict';

    // Opret modal container hvis den ikke findes
    function ensureModalContainer() {
        let container = document.getElementById('modal-utils-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'modal-utils-container';
            container.innerHTML = `
                <style>
                    .mu-overlay {
                        position: fixed;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        background: rgba(0,0,0,0.5);
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        z-index: 10000;
                        opacity: 0;
                        transition: opacity 0.2s ease;
                    }
                    .mu-overlay.visible {
                        opacity: 1;
                    }
                    .mu-dialog {
                        background: white;
                        border-radius: 12px;
                        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                        width: 90%;
                        max-width: 450px;
                        transform: scale(0.9);
                        transition: transform 0.2s ease;
                    }
                    .mu-overlay.visible .mu-dialog {
                        transform: scale(1);
                    }
                    .mu-header {
                        padding: 20px 24px 0;
                    }
                    .mu-header h3 {
                        margin: 0;
                        font-size: 1.2rem;
                        color: #1f2937;
                        display: flex;
                        align-items: center;
                        gap: 10px;
                    }
                    .mu-header.danger h3 {
                        color: #dc2626;
                    }
                    .mu-body {
                        padding: 16px 24px 24px;
                    }
                    .mu-body p {
                        margin: 0 0 16px;
                        color: #4b5563;
                        font-size: 0.95rem;
                        line-height: 1.5;
                    }
                    .mu-input-group {
                        margin-bottom: 16px;
                    }
                    .mu-input-group label {
                        display: block;
                        margin-bottom: 6px;
                        font-size: 0.9rem;
                        color: #374151;
                        font-weight: 500;
                    }
                    .mu-input-group input {
                        width: 100%;
                        padding: 10px 14px;
                        border: 2px solid #e5e7eb;
                        border-radius: 8px;
                        font-size: 1rem;
                        transition: border-color 0.2s;
                        box-sizing: border-box;
                    }
                    .mu-input-group input:focus {
                        outline: none;
                        border-color: #3b82f6;
                    }
                    .mu-input-group.error input {
                        border-color: #dc2626;
                    }
                    .mu-input-group .hint {
                        margin-top: 6px;
                        font-size: 0.85rem;
                        color: #6b7280;
                    }
                    .mu-input-group .hint code {
                        background: #f3f4f6;
                        padding: 2px 6px;
                        border-radius: 4px;
                        font-family: monospace;
                    }
                    .mu-footer {
                        padding: 16px 24px;
                        background: #f9fafb;
                        border-radius: 0 0 12px 12px;
                        display: flex;
                        gap: 12px;
                        justify-content: flex-end;
                    }
                    .mu-btn {
                        padding: 10px 20px;
                        border-radius: 8px;
                        font-size: 0.95rem;
                        font-weight: 500;
                        cursor: pointer;
                        transition: all 0.2s;
                        border: none;
                    }
                    .mu-btn-cancel {
                        background: white;
                        border: 1px solid #d1d5db;
                        color: #374151;
                    }
                    .mu-btn-cancel:hover {
                        background: #f3f4f6;
                    }
                    .mu-btn-danger {
                        background: #dc2626;
                        color: white;
                    }
                    .mu-btn-danger:hover:not(:disabled) {
                        background: #b91c1c;
                    }
                    .mu-btn-danger:disabled {
                        background: #fca5a5;
                        cursor: not-allowed;
                    }
                    .mu-btn-primary {
                        background: #3b82f6;
                        color: white;
                    }
                    .mu-btn-primary:hover {
                        background: #2563eb;
                    }
                </style>
            `;
            document.body.appendChild(container);
        }
        return container;
    }

    /**
     * Vis en bekræftelses-dialog med input-felt
     *
     * @param {Object} options
     * @param {string} options.title - Dialogens titel
     * @param {string} options.message - Beskrivende tekst
     * @param {string} options.confirmText - Den tekst brugeren skal skrive
     * @param {string} options.confirmLabel - Label over input-feltet
     * @param {string} options.confirmButton - Tekst på bekræft-knappen (default: "Slet")
     * @param {string} options.cancelButton - Tekst på annuller-knappen (default: "Annuller")
     * @param {boolean} options.danger - Om det er en farlig handling (rød styling)
     * @returns {Promise<boolean>} - true hvis bekræftet, false hvis annulleret
     */
    function confirmWithInput(options) {
        return new Promise((resolve) => {
            const container = ensureModalContainer();

            const overlay = document.createElement('div');
            overlay.className = 'mu-overlay';
            overlay.innerHTML = `
                <div class="mu-dialog">
                    <div class="mu-header ${options.danger ? 'danger' : ''}">
                        <h3>${options.danger ? '⚠️ ' : ''}${options.title}</h3>
                    </div>
                    <div class="mu-body">
                        <p>${options.message}</p>
                        <div class="mu-input-group">
                            <label>${options.confirmLabel || 'Skriv for at bekræfte'}</label>
                            <input type="text" id="mu-confirm-input" autocomplete="off" spellcheck="false">
                            <div class="hint">Skriv <code>${options.confirmText}</code> for at bekræfte</div>
                        </div>
                    </div>
                    <div class="mu-footer">
                        <button class="mu-btn mu-btn-cancel" id="mu-cancel">${options.cancelButton || 'Annuller'}</button>
                        <button class="mu-btn ${options.danger ? 'mu-btn-danger' : 'mu-btn-primary'}" id="mu-confirm" disabled>
                            ${options.confirmButton || 'Bekræft'}
                        </button>
                    </div>
                </div>
            `;

            container.appendChild(overlay);

            // Fade in
            requestAnimationFrame(() => {
                overlay.classList.add('visible');
            });

            const input = overlay.querySelector('#mu-confirm-input');
            const confirmBtn = overlay.querySelector('#mu-confirm');
            const cancelBtn = overlay.querySelector('#mu-cancel');

            // Focus input
            setTimeout(() => input.focus(), 100);

            // Check input match
            input.addEventListener('input', () => {
                const matches = input.value === options.confirmText;
                confirmBtn.disabled = !matches;
            });

            // Enter-key support
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && input.value === options.confirmText) {
                    cleanup();
                    resolve(true);
                }
            });

            // Escape-key support
            overlay.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    cleanup();
                    resolve(false);
                }
            });

            function cleanup() {
                overlay.classList.remove('visible');
                setTimeout(() => overlay.remove(), 200);
            }

            cancelBtn.addEventListener('click', () => {
                cleanup();
                resolve(false);
            });

            confirmBtn.addEventListener('click', () => {
                cleanup();
                resolve(true);
            });

            // Click outside to cancel
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    cleanup();
                    resolve(false);
                }
            });
        });
    }

    /**
     * Vis en simpel alert-dialog
     *
     * @param {Object} options
     * @param {string} options.title - Dialogens titel
     * @param {string} options.message - Beskrivende tekst
     * @param {string} options.buttonText - Tekst på knappen (default: "OK")
     * @returns {Promise<void>}
     */
    function alertModal(options) {
        return new Promise((resolve) => {
            const container = ensureModalContainer();

            const overlay = document.createElement('div');
            overlay.className = 'mu-overlay';
            overlay.innerHTML = `
                <div class="mu-dialog">
                    <div class="mu-header">
                        <h3>${options.title}</h3>
                    </div>
                    <div class="mu-body">
                        <p>${options.message}</p>
                    </div>
                    <div class="mu-footer">
                        <button class="mu-btn mu-btn-primary" id="mu-ok">${options.buttonText || 'OK'}</button>
                    </div>
                </div>
            `;

            container.appendChild(overlay);

            requestAnimationFrame(() => {
                overlay.classList.add('visible');
            });

            const okBtn = overlay.querySelector('#mu-ok');
            setTimeout(() => okBtn.focus(), 100);

            function cleanup() {
                overlay.classList.remove('visible');
                setTimeout(() => overlay.remove(), 200);
            }

            okBtn.addEventListener('click', () => {
                cleanup();
                resolve();
            });

            overlay.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' || e.key === 'Enter') {
                    cleanup();
                    resolve();
                }
            });
        });
    }

    // Eksporter til global scope
    window.ModalUtils = {
        confirmWithInput,
        alertModal
    };

})(window);
