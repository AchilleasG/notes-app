/**
 * Client-side encryption/decryption for notes
 * Uses Web Crypto API for secure encryption
 */

class NoteEncryption {
    constructor() {
        // Store passwords in memory only (cleared on page refresh)
        this.passwordCache = new Map();
        this.algorithm = 'AES-GCM';
        this.keyLength = 256;
        this.ivLength = 12; // 96 bits for AES-GCM
        this.saltLength = 16; // 128 bits
        this.iterations = 100000; // PBKDF2 iterations
    }

    /**
     * Generate a random salt
     */
    generateSalt() {
        return crypto.getRandomValues(new Uint8Array(this.saltLength));
    }

    /**
     * Generate a random IV
     */
    generateIV() {
        return crypto.getRandomValues(new Uint8Array(this.ivLength));
    }

    /**
     * Derive a key from password and salt using PBKDF2
     */
    async deriveKey(password, salt) {
        const encoder = new TextEncoder();
        const passwordKey = await crypto.subtle.importKey(
            'raw',
            encoder.encode(password),
            'PBKDF2',
            false,
            ['deriveKey']
        );

        return crypto.subtle.deriveKey(
            {
                name: 'PBKDF2',
                salt: salt,
                iterations: this.iterations,
                hash: 'SHA-256'
            },
            passwordKey,
            {
                name: this.algorithm,
                length: this.keyLength
            },
            false,
            ['encrypt', 'decrypt']
        );
    }

    /**
     * Encrypt text with password
     */
    async encrypt(text, password) {
        try {
            const encoder = new TextEncoder();
            const data = encoder.encode(text);

            const salt = this.generateSalt();
            const iv = this.generateIV();
            const key = await this.deriveKey(password, salt);

            const encryptedData = await crypto.subtle.encrypt(
                {
                    name: this.algorithm,
                    iv: iv
                },
                key,
                data
            );

            // Combine salt + iv + encrypted data
            const result = new Uint8Array(salt.length + iv.length + encryptedData.byteLength);
            result.set(salt, 0);
            result.set(iv, salt.length);
            result.set(new Uint8Array(encryptedData), salt.length + iv.length);

            // Return base64 encoded result and salt as hex for storage
            return {
                encrypted: btoa(String.fromCharCode(...result)),
                salt: Array.from(salt).map(b => b.toString(16).padStart(2, '0')).join('')
            };
        } catch (error) {
            console.error('Encryption failed:', error);
            throw new Error('Failed to encrypt content');
        }
    }

    /**
     * Decrypt text with password
     */
    async decrypt(encryptedText, password, saltHex) {
        try {
            // Convert base64 back to bytes
            const combined = new Uint8Array(atob(encryptedText).split('').map(c => c.charCodeAt(0)));

            // Extract salt from hex
            const salt = new Uint8Array(saltHex.match(/.{2}/g).map(byte => parseInt(byte, 16)));

            // Extract IV and encrypted data
            const iv = combined.slice(this.saltLength, this.saltLength + this.ivLength);
            const encryptedData = combined.slice(this.saltLength + this.ivLength);

            const key = await this.deriveKey(password, salt);

            const decryptedData = await crypto.subtle.decrypt(
                {
                    name: this.algorithm,
                    iv: iv
                },
                key,
                encryptedData
            );

            const decoder = new TextDecoder();
            return decoder.decode(decryptedData);
        } catch (error) {
            console.error('Decryption failed:', error);
            throw new Error('Failed to decrypt content - wrong password?');
        }
    }

    /**
     * Cache password for a note
     */
    cachePassword(noteId, password) {
        this.passwordCache.set(noteId, password);
    }

    /**
     * Get cached password for a note
     */
    getCachedPassword(noteId) {
        return this.passwordCache.get(noteId);
    }

    /**
     * Clear cached password for a note
     */
    clearCachedPassword(noteId) {
        this.passwordCache.delete(noteId);
    }

    /**
     * Clear all cached passwords
     */
    clearAllPasswords() {
        this.passwordCache.clear();
    }
}

// Global instance
window.noteEncryption = new NoteEncryption();

// Clear passwords when page is about to unload
window.addEventListener('beforeunload', () => {
    window.noteEncryption.clearAllPasswords();
});

// Clear passwords on page hide (mobile/tab switching)
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        // Optional: clear passwords when tab becomes hidden
        // window.noteEncryption.clearAllPasswords();
    }
});
