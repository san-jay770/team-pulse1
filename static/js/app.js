/**
 * TEAM PULSE - Interactive Client JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
    initMobileSidebar();
    initFlashAlerts();
    initPasswordToggles();
    initDeleteConfirmations();
    initDynamicTaskMembers();
    initTeamSwitcher();
    initUserEmailLookup();
    initFormSubmissions();
});

/**
 * Mobile Sidebar Drawer Navigation
 */
function initMobileSidebar() {
    const toggleBtn = document.getElementById('menuToggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');

    if (!toggleBtn || !sidebar) return;

    function openSidebar() {
        sidebar.classList.add('open');
        if (overlay) overlay.classList.add('open');
        document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
        sidebar.classList.remove('open');
        if (overlay) overlay.classList.remove('open');
        document.body.style.overflow = '';
    }

    toggleBtn.addEventListener('click', () => {
        if (sidebar.classList.contains('open')) {
            closeSidebar();
        } else {
            openSidebar();
        }
    });

    if (overlay) {
        overlay.addEventListener('click', closeSidebar);
    }
}

/**
 * Top Navbar Team Switcher Dropdown
 */
function initTeamSwitcher() {
    const switcherBtn = document.getElementById('teamSwitcherBtn');
    const switcherMenu = document.getElementById('teamSwitcherMenu');

    if (!switcherBtn || !switcherMenu) return;

    switcherBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = switcherMenu.style.display === 'block';
        switcherMenu.style.display = isOpen ? 'none' : 'block';
    });

    document.addEventListener('click', (e) => {
        if (!switcherMenu.contains(e.target) && e.target !== switcherBtn) {
            switcherMenu.style.display = 'none';
        }
    });
}

/**
 * Live User Email Check on User Form
 */
function initUserEmailLookup() {
    const emailInput = document.getElementById('email');
    const nameInput = document.getElementById('name');
    const banner = document.getElementById('existingUserBanner');
    const foundNameSpan = document.getElementById('foundUserName');
    const foundTeamsSpan = document.getElementById('foundUserTeams');
    const passNote = document.getElementById('passwordRequiredNote');
    const passInput = document.getElementById('password');

    if (!emailInput || !banner) return;

    let debounceTimer = null;

    async function checkEmail() {
        const val = emailInput.value.trim();
        if (!val || val.indexOf('@') === -1) {
            banner.style.display = 'none';
            if (passNote) passNote.textContent = '(Required for new users, optional for existing)';
            return;
        }

        try {
            const resp = await fetch(`/api/user-by-email?email=${encodeURIComponent(val)}`);
            if (!resp.ok) return;
            const data = await resp.json();

            if (data.found) {
                banner.style.display = 'block';
                if (foundNameSpan) foundNameSpan.textContent = data.name;
                if (foundTeamsSpan) foundTeamsSpan.textContent = data.current_teams;
                if (passNote) passNote.textContent = '(Optional — existing credentials will be retained)';
                if (nameInput && (!nameInput.value.trim() || nameInput.value === nameInput.defaultValue)) {
                    nameInput.value = data.name;
                }
                if (passInput) {
                    passInput.placeholder = 'Leave blank to preserve existing password';
                }
            } else {
                banner.style.display = 'none';
                if (passNote) passNote.textContent = '(Required for new users)';
                if (passInput) {
                    passInput.placeholder = '••••••••';
                }
            }
        } catch (err) {
            console.error('Email lookup error:', err);
        }
    }

    emailInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(checkEmail, 300);
    });

    emailInput.addEventListener('change', checkEmail);

    // Initial check if preset
    if (emailInput.value.trim()) {
        checkEmail();
    }
}

/**
 * Flash Alert Messages Auto-Dismiss
 */
function initFlashAlerts() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        const closeBtn = alert.querySelector('.alert-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                alert.style.opacity = '0';
                setTimeout(() => alert.remove(), 300);
            });
        }

        // Auto hide after 5 seconds
        setTimeout(() => {
            if (document.body.contains(alert)) {
                alert.style.opacity = '0';
                setTimeout(() => alert.remove(), 300);
            }
        }, 5000);
    });
}

/**
 * Password Field Visibility Toggle
 */
function initPasswordToggles() {
    const toggleButtons = document.querySelectorAll('.password-toggle-btn');
    toggleButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = btn.getAttribute('data-target');
            const input = targetId ? document.getElementById(targetId) : btn.previousElementSibling;
            
            if (input && (input.type === 'password' || input.type === 'text')) {
                const isPassword = input.type === 'password';
                input.type = isPassword ? 'text' : 'password';
                btn.textContent = isPassword ? 'Hide' : 'Show';
            }
        });
    });
}

/**
 * Delete Action Confirmation Modal
 */
function initDeleteConfirmations() {
    const deleteForms = document.querySelectorAll('form[data-confirm]');
    deleteForms.forEach(form => {
        form.addEventListener('submit', (e) => {
            const message = form.getAttribute('data-confirm') || 'Are you sure you want to delete this item? This action cannot be undone.';
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });
}

/**
 * Dynamic Task Member Selection based on Selected Team
 * Endpoint: /tasks/members/<team_id>
 */
function initDynamicTaskMembers() {
    const teamSelect = document.getElementById('taskTeamSelect');
    const memberSelect = document.getElementById('taskMemberSelect');

    if (!teamSelect || !memberSelect) return;

    teamSelect.addEventListener('change', async () => {
        const teamId = teamSelect.value;
        if (!teamId) {
            memberSelect.innerHTML = '<option value="">-- Select Member --</option>';
            return;
        }

        memberSelect.disabled = true;
        const defaultOption = memberSelect.querySelector('option[value=""]');
        if (defaultOption) defaultOption.textContent = 'Loading members...';

        try {
            const response = await fetch(`/tasks/members/${teamId}`);
            if (!response.ok) throw new Error('Failed to load team members');

            const data = await response.json();
            const currentSelected = memberSelect.getAttribute('data-current');

            memberSelect.innerHTML = '<option value="">Unassigned</option>';

            if (data.members && data.members.length > 0) {
                data.members.forEach(member => {
                    const option = document.createElement('option');
                    option.value = member.id;
                    option.textContent = member.name;
                    if (currentSelected && String(currentSelected) === String(member.id)) {
                        option.selected = true;
                    }
                    memberSelect.appendChild(option);
                });
            } else {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = 'No members in this team';
                memberSelect.appendChild(option);
            }
        } catch (err) {
            console.error('Error fetching team members:', err);
            memberSelect.innerHTML = '<option value="">Error loading members</option>';
        } finally {
            memberSelect.disabled = false;
        }
    });
}

/**
 * Form Submit Spinner / Loading State
 */
function initFormSubmissions() {
    const forms = document.querySelectorAll('form:not([data-confirm])');
    forms.forEach(form => {
        form.addEventListener('submit', () => {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                const originalText = submitBtn.innerHTML;
                submitBtn.innerHTML = `
                    <svg class="spin" style="width:16px;height:16px;margin-right:6px;animation:spin 1s linear infinite;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
                        <path d="M12 2a10 10 0 0 1 10 10" stroke-opacity="1"></path>
                    </svg>
                    Processing...
                `;
            }
        });
    });
}
