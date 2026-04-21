/**
 * Security Interface Helper - Display security info and validate policies
 * Usage: Include in templates and call SecurityUI.displayPasswordPolicy(elementId)
 */

const SecurityUI = {
    /**
     * Display password policy in a given element
     */
    displayPasswordPolicy(targetElementId) {
        const el = document.getElementById(targetElementId);
        if (!el) return;
        
        el.innerHTML = `
            <div style="padding: 1rem; background: rgba(183, 135, 60, 0.1); border-left: 3px solid #b08a34; border-radius: 4px;">
                <strong style="color: #8a6a1f;">🔐 Password Policy Requirements</strong>
                <ul style="margin: 0.5rem 0 0 0; padding-left: 1.5rem; font-size: 0.9rem;">
                    <li>Minimum 10 characters</li>
                    <li>No leading or trailing spaces</li>
                    <li>Must be different from current password</li>
                </ul>
            </div>
        `;
    },

    /**
     * Display login rate limit info
     */
    displayRateLimitInfo(targetElementId) {
        const el = document.getElementById(targetElementId);
        if (!el) return;
        
        el.innerHTML = `
            <div style="padding: 1rem; background: rgba(199, 73, 69, 0.08); border-left: 3px solid #c74945; border-radius: 4px;">
                <strong style="color: #1768c6;">⏱️ Rate Limiting</strong>
                <p style="margin: 0.5rem 0 0 0; font-size: 0.9rem;">
                    Account will lock for 10 minutes after 5 failed login attempts within a 15-minute window.
                </p>
            </div>
        `;
    },

    /**
     * Validate password policy in real-time
     */
    validatePassword(passwordValue) {
        const errors = [];
        
        if (passwordValue.length < 10) {
            errors.push({
                type: 'length',
                message: `Too short (${passwordValue.length}/10 characters)`,
                severity: 'error'
            });
        }
        
        if (passwordValue !== passwordValue.trim()) {
            errors.push({
                type: 'whitespace',
                message: 'Remove leading or trailing spaces',
                severity: 'error'
            });
        }
        
        if (passwordValue.length >= 10 && passwordValue === passwordValue.trim()) {
            return {
                valid: true,
                message: '✓ Password meets all requirements',
                errors: []
            };
        }
        
        return {
            valid: false,
            message: errors.length > 0 ? errors[0].message : 'Invalid password',
            errors: errors
        };
    },

    /**
     * Apply real-time validation to password input
     */
    setupPasswordValidation(inputId, feedbackId) {
        const input = document.getElementById(inputId);
        const feedback = document.getElementById(feedbackId);
        
        if (!input || !feedback) return;
        
        input.addEventListener('input', () => {
            const result = SecurityUI.validatePassword(input.value);
            
            if (input.value.length === 0) {
                feedback.textContent = '';
                feedback.style.color = 'inherit';
            } else if (result.valid) {
                feedback.innerHTML = '✓ ' + result.message;
                feedback.style.color = '#2f7757';
            } else {
                feedback.innerHTML = '⚠ ' + result.message;
                feedback.style.color = '#c74945';
            }
        });
    },

    /**
     * Setup multiple password fields validation
     */
    setupBulkPasswordValidation(selectors) {
        document.querySelectorAll(selectors).forEach(input => {
            input.addEventListener('input', function() {
                const result = SecurityUI.validatePassword(this.value);
                const feedback = this.nextElementSibling;
                
                if (feedback && feedback.classList.contains('password-policy-feedback')) {
                    if (this.value.length === 0) {
                        feedback.textContent = '';
                    } else if (result.valid) {
                        feedback.innerHTML = '✓ ' + result.message;
                        feedback.style.color = '#2f7757';
                    } else {
                        feedback.innerHTML = '⚠ ' + result.message;
                        feedback.style.color = '#c74945';
                    }
                }
            });
        });
    },

    /**
     * Show modal/toast with security info
     */
    showSecurityInfo(title, content) {
        const modal = document.createElement('div');
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
        `;
        
        const card = document.createElement('div');
        card.style.cssText = `
            background: white;
            border-radius: 8px;
            padding: 2rem;
            max-width: 500px;
            width: 90%;
            box-shadow: 0 24px 54px rgba(33, 20, 56, 0.25);
        `;
        
        card.innerHTML = `
            <h2 style="margin: 0 0 1rem 0; color: #1b3f76;">${title}</h2>
            <div style="color: #395a8c; line-height: 1.6; margin-bottom: 1.5rem;">${content}</div>
            <button onclick="this.parentElement.parentElement.remove()" style="
                background: #1768c6;
                color: white;
                border: none;
                padding: 0.5rem 1rem;
                border-radius: 4px;
                cursor: pointer;
                font-weight: 600;
            ">Close</button>
        `;
        
        modal.appendChild(card);
        document.body.appendChild(modal);
    },

    /**
     * Get local security config from page meta tags
     */
    getSecurityConfig() {
        return {
            minPasswordLength: parseInt(document.head.querySelector('meta[name="security-min-password-length"]')?.content || '10'),
            loginMaxFailures: parseInt(document.head.querySelector('meta[name="security-login-max-failures"]')?.content || '5'),
            loginLockSeconds: parseInt(document.head.querySelector('meta[name="security-login-lock-seconds"]')?.content || '600'),
            loginWindowSeconds: parseInt(document.head.querySelector('meta[name="security-login-window-seconds"]')?.content || '900'),
        };
    }
};

// Export for module usage if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SecurityUI;
}
