// Page navigation progress bar
function initPageProgress() {
    const progressBar = document.getElementById('page-progress');
    if (!progressBar) return;

    let progressInterval;
    let progress = 0;

    function startProgress() {
        progress = 0;
        progressBar.style.width = '0%';
        progressBar.classList.add('loading');
        document.body.classList.add('navigating');

        progressInterval = setInterval(() => {
            progress += Math.random() * 30;
            if (progress > 90) progress = 90;
            progressBar.style.width = progress + '%';
        }, 150);
    }

    function completeProgress() {
        clearInterval(progressInterval);
        progressBar.style.width = '100%';
        setTimeout(() => {
            progressBar.classList.remove('loading');
            progressBar.style.width = '0%';
            document.body.classList.remove('navigating');
        }, 300);
    }

    // Intercept navigation clicks
    document.addEventListener('click', (e) => {
        const link = e.target.closest('a[href]');
        if (!link) return;

        const href = link.getAttribute('href');
        // Skip external links, anchors, and special links
        if (
            href.startsWith('http') ||
            href.startsWith('#') ||
            href.startsWith('mailto:') ||
            href.startsWith('tel:') ||
            link.hasAttribute('target') ||
            link.hasAttribute('download') ||
            e.ctrlKey || e.metaKey || e.shiftKey
        ) {
            return;
        }

        // Check if it's a same-origin navigation
        const url = new URL(href, window.location.origin);
        if (url.origin === window.location.origin && url.pathname !== window.location.pathname) {
            e.preventDefault();
            startProgress();
            window.location.href = href;
        }
    });

    // Complete progress when page is loaded/hidden
    window.addEventListener('pagehide', completeProgress);
    window.addEventListener('beforeunload', completeProgress);
}

function initChangePasswordBottomSheet() {
    const actionBtn = document.getElementById('changePasswordBtn');
    const bottomSheet = document.getElementById('changePasswordBottomSheet');
    const backdrop = document.getElementById('changePasswordSheetBackdrop');
    const sheet = document.getElementById('changePasswordSheet');
    const closeBtn = document.getElementById('changePasswordSheetClose');
    const handle = document.getElementById('changePasswordSheetHandle');

    if (!bottomSheet || !backdrop || !sheet || !closeBtn || !handle) {
        return;
    }

    let scrollLockY = 0;

    function lockScroll() {
        scrollLockY = window.scrollY || 0;
        document.body.style.position = 'fixed';
        document.body.style.top = `-${scrollLockY}px`;
        document.body.style.left = '0';
        document.body.style.right = '0';
        document.body.style.width = '100%';
        document.body.style.overflow = 'hidden';
    }

    function unlockScroll() {
        document.body.style.position = '';
        const top = document.body.style.top;
        document.body.style.top = '';
        document.body.style.left = '';
        document.body.style.right = '';
        document.body.style.width = '';
        document.body.style.overflow = '';
        const y = top ? Math.abs(parseInt(top, 10)) : scrollLockY;
        window.scrollTo(0, Number.isFinite(y) ? y : 0);
    }

    function openSheet() {
        lockScroll();
        bottomSheet.classList.remove('opacity-0', 'pointer-events-none');
        bottomSheet.classList.add('opacity-100');
        sheet.classList.remove('translate-y-full');
        backdrop.classList.remove('pointer-events-none');
        backdrop.classList.add('pointer-events-auto');
    }

    function closeSheet() {
        bottomSheet.classList.add('opacity-0', 'pointer-events-none');
        bottomSheet.classList.remove('opacity-100');
        sheet.classList.add('translate-y-full');
        backdrop.classList.add('pointer-events-none');
        backdrop.classList.remove('pointer-events-auto');
        unlockScroll();
    }

    if (actionBtn) {
        actionBtn.addEventListener('click', openSheet);
    }
    closeBtn.addEventListener('click', closeSheet);
    backdrop.addEventListener('click', closeSheet);

    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeSheet();
        }
    });

    // Swipe down to close
    let startY = 0;
    let isDragging = false;
    let dragStartTime = 0;

    function onStart(e) {
        const t = e.touches ? e.touches[0] : e;
        startY = t.clientY;
        isDragging = true;
        dragStartTime = Date.now();
        sheet.style.transition = 'none';
    }

    function onMove(e) {
        if (!isDragging) return;
        const t = e.touches ? e.touches[0] : e;
        const dy = t.clientY - startY;
        if (dy > 0) {
            sheet.style.transform = `translateY(${dy}px)`;
        }
    }

    function onEnd(e) {
        if (!isDragging) return;
        isDragging = false;
        sheet.style.transition = '';

        const endY = (e.changedTouches ? e.changedTouches[0] : e).clientY;
        const dy = endY - startY;
        const dt = Date.now() - dragStartTime;

        if (dy > 120 || (dy > 60 && dt < 250)) {
            sheet.style.transform = '';
            closeSheet();
            return;
        }

        sheet.style.transform = '';
    }

    handle.addEventListener('touchstart', onStart, { passive: true });
    handle.addEventListener('touchmove', onMove, { passive: true });
    handle.addEventListener('touchend', onEnd, { passive: true });
    handle.addEventListener('mousedown', onStart);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onEnd);

    // Auto-open when server sent message
    const autoOpen = bottomSheet.getAttribute('data-auto-open') === '1';
    if (autoOpen) {
        setTimeout(openSheet, 50);
    }
}

function initAdminChangePasswordBottomSheet() {
    const actionBtn = document.getElementById('adminChangePasswordBtn');
    const actionBtnMobile = document.getElementById('adminChangePasswordBtnMobile');
    const actionBtnSidebar = document.getElementById('adminChangePasswordBtnSidebar');
    const bottomSheet = document.getElementById('adminChangePasswordBottomSheet');
    const backdrop = document.getElementById('adminChangePasswordSheetBackdrop');
    const sheet = document.getElementById('adminChangePasswordSheet');
    const closeBtn = document.getElementById('adminChangePasswordSheetClose');
    const handle = document.getElementById('adminChangePasswordSheetHandle');

    if (!bottomSheet || !backdrop || !sheet || !closeBtn || !handle) {
        return;
    }

    let scrollLockY = 0;

    function lockScroll() {
        scrollLockY = window.scrollY || 0;
        document.body.style.position = 'fixed';
        document.body.style.top = `-${scrollLockY}px`;
        document.body.style.left = '0';
        document.body.style.right = '0';
        document.body.style.width = '100%';
        document.body.style.overflow = 'hidden';
    }

    function unlockScroll() {
        document.body.style.position = '';
        const top = document.body.style.top;
        document.body.style.top = '';
        document.body.style.left = '';
        document.body.style.right = '';
        document.body.style.width = '';
        document.body.style.overflow = '';
        const y = top ? Math.abs(parseInt(top, 10)) : scrollLockY;
        window.scrollTo(0, Number.isFinite(y) ? y : 0);
    }

    function openSheet() {
        lockScroll();
        bottomSheet.classList.remove('opacity-0', 'pointer-events-none');
        bottomSheet.classList.add('opacity-100');
        sheet.classList.remove('translate-y-full');
        backdrop.classList.remove('pointer-events-none');
        backdrop.classList.add('pointer-events-auto');
    }

    function closeSheet() {
        bottomSheet.classList.add('opacity-0', 'pointer-events-none');
        bottomSheet.classList.remove('opacity-100');
        sheet.classList.add('translate-y-full');
        backdrop.classList.add('pointer-events-none');
        backdrop.classList.remove('pointer-events-auto');
        unlockScroll();
    }

    [actionBtn, actionBtnMobile, actionBtnSidebar].forEach((btn) => {
        if (!btn) return;
        btn.addEventListener('click', openSheet);
    });
    closeBtn.addEventListener('click', closeSheet);
    backdrop.addEventListener('click', closeSheet);

    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeSheet();
        }
    });

    // Swipe down to close
    let startY = 0;
    let isDragging = false;
    let dragStartTime = 0;

    function onStart(e) {
        const t = e.touches ? e.touches[0] : e;
        startY = t.clientY;
        isDragging = true;
        dragStartTime = Date.now();
        sheet.style.transition = 'none';
    }

    function onMove(e) {
        if (!isDragging) return;
        const t = e.touches ? e.touches[0] : e;
        const dy = t.clientY - startY;
        if (dy > 0) {
            sheet.style.transform = `translateY(${dy}px)`;
        }
    }

    function onEnd(e) {
        if (!isDragging) return;
        isDragging = false;
        sheet.style.transition = '';

        const endY = (e.changedTouches ? e.changedTouches[0] : e).clientY;
        const dy = endY - startY;
        const dt = Date.now() - dragStartTime;

        if (dy > 120 || (dy > 60 && dt < 250)) {
            sheet.style.transform = '';
            closeSheet();
            return;
        }

        sheet.style.transform = '';
    }

    handle.addEventListener('touchstart', onStart, { passive: true });
    handle.addEventListener('touchmove', onMove, { passive: true });
    handle.addEventListener('touchend', onEnd, { passive: true });
    handle.addEventListener('mousedown', onStart);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onEnd);

    // Auto-open when server sent message
    const autoOpen = bottomSheet.getAttribute('data-auto-open') === '1';
    if (autoOpen) {
        setTimeout(openSheet, 50);
    }
}

function generateAttendance() {
    const grid = document.getElementById('attendanceGrid');
    if (!grid) {
        return;
    }
    const days = 7;
    const weeks = 28;

    let levels = [];
    const levelsScript = document.getElementById('attendanceLevels');
    if (levelsScript && levelsScript.textContent) {
        try {
            const parsed = JSON.parse(levelsScript.textContent);
            if (Array.isArray(parsed)) {
                levels = parsed;
            }
        } catch {
            levels = [];
        }
    }

    for (let i = 0; i < days * weeks; i++) {
        const cell = document.createElement('div');
        cell.className = 'attendance-cell';

        const raw = levels[i];
        const level = Number.isFinite(Number(raw)) ? Math.max(0, Math.min(4, Number(raw))) : 0;
        cell.classList.add(`level-${level}`);

        const dayStr = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][i % 7];
        cell.title = `${dayStr} Attendance Level: ${level}/4`;

        grid.appendChild(cell);
    }
}

function applyAttendanceRings() {
    document.querySelectorAll('.attendance-ring[data-percentage]').forEach((el) => {
        const value = Number(el.dataset.percentage);
        const pct = Number.isFinite(value) ? value : 0;
        el.style.setProperty('--percentage', String(pct));
    });
}

function initWeeklyTimetable() {
    const root = document.querySelector('[data-weekly-timetable]');
    if (!root) {
        return;
    }

    const panels = root.querySelector('[data-week-panels]');
    if (!panels) {
        return;
    }

    const tabs = Array.from(root.querySelectorAll('[data-week-tab]'));

    function setActiveTab(index) {
        tabs.forEach((btn) => {
            const isActive = Number(btn.dataset.weekTab) === index;
            btn.classList.toggle('bg-indigo-50', isActive);
            btn.classList.toggle('text-indigo-600', isActive);
            btn.classList.toggle('bg-slate-100', !isActive);
            btn.classList.toggle('text-slate-700', !isActive);
        });
    }

    function scrollToIndex(index) {
        const width = panels.clientWidth || 1;
        panels.scrollTo({ left: index * width, behavior: 'smooth' });
    }

    tabs.forEach((btn) => {
        btn.addEventListener('click', () => {
            const index = Number(btn.dataset.weekTab);
            if (Number.isFinite(index)) {
                scrollToIndex(index);
                setActiveTab(index);
            }
        });
    });

    let raf = 0;
    panels.addEventListener('scroll', () => {
        if (raf) {
            return;
        }
        raf = window.requestAnimationFrame(() => {
            raf = 0;
            const width = panels.clientWidth || 1;
            const index = Math.round(panels.scrollLeft / width);
            setActiveTab(index);
        });
    }, { passive: true });

    window.addEventListener('resize', () => {
        const current = Number(root.dataset.activeDay || root.dataset.initialDay || 0);
        if (Number.isFinite(current)) {
            panels.scrollLeft = (panels.clientWidth || 1) * current;
        }
    });

    const initial = Number(root.dataset.initialDay || 0);
    root.dataset.activeDay = String(Number.isFinite(initial) ? initial : 0);
    setActiveTab(Number(root.dataset.activeDay));
    panels.scrollLeft = (panels.clientWidth || 1) * Number(root.dataset.activeDay);
}

function initScheduleCalendarSheet() {
    const calendarRoot = document.querySelector('[data-schedule-calendar]');
    if (!calendarRoot) {
        return;
    }

    const backdrop = document.querySelector('[data-bottom-sheet-backdrop]');
    const sheet = document.querySelector('[data-bottom-sheet]');
    const closeBtn = document.querySelector('[data-sheet-close]');
    const titleEl = document.querySelector('[data-sheet-title]');
    const dateLabelEl = document.querySelector('[data-sheet-date-label]');
    const sectionsEl = document.querySelector('[data-sheet-sections]');
    const handleEl = document.querySelector('[data-sheet-handle]');

    if (!backdrop || !sheet || !closeBtn || !titleEl || !dateLabelEl || !sectionsEl || !handleEl) {
        return;
    }

    let scrollLockY = 0;
    function lockScroll() {
        scrollLockY = window.scrollY || 0;
        document.body.style.position = 'fixed';
        document.body.style.top = `-${scrollLockY}px`;
        document.body.style.left = '0';
        document.body.style.right = '0';
        document.body.style.width = '100%';
        document.body.style.overflow = 'hidden';
    }

    function unlockScroll() {
        document.body.style.position = '';
        const top = document.body.style.top;
        document.body.style.top = '';
        document.body.style.left = '';
        document.body.style.right = '';
        document.body.style.width = '';
        document.body.style.overflow = '';
        const y = top ? Math.abs(parseInt(top, 10)) : scrollLockY;
        window.scrollTo(0, Number.isFinite(y) ? y : 0);
    }

    let timetableData = {};
    const timetableScript = document.getElementById('timetableData');
    if (timetableScript && timetableScript.textContent) {
        try {
            timetableData = JSON.parse(timetableScript.textContent);
        } catch {
            timetableData = {};
        }
    }

    function openSheet() {
        lockScroll();
        backdrop.classList.remove('opacity-0', 'pointer-events-none');
        backdrop.classList.add('opacity-100');
        sheet.classList.remove('translate-y-full', 'opacity-0', 'pointer-events-none');
        sheet.classList.add('opacity-100');
        sheet.style.transform = '';
    }

    function closeSheet() {
        backdrop.classList.add('opacity-0', 'pointer-events-none');
        backdrop.classList.remove('opacity-100');
        sheet.classList.add('translate-y-full', 'opacity-0', 'pointer-events-none');
        sheet.classList.remove('opacity-100');
        sheet.style.transform = '';
        unlockScroll();
    }

    function esc(s) {
        return String(s)
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#39;');
    }

    function buildSection(label, html) {
        const wrapper = document.createElement('div');
        wrapper.className = 'p-4 rounded-xl border border-slate-200 bg-white';
        wrapper.innerHTML = `<p class="text-sm font-semibold text-slate-900 mb-2">${esc(label)}</p>${html}`;
        return wrapper;
    }

    function renderForDate(dateStr, items, events) {
        const dt = new Date(`${dateStr}T00:00:00`);
        const jsDow = dt.getDay();
        const dow = (jsDow + 6) % 7;
        const classes = timetableData[String(dow)] || [];

        dateLabelEl.textContent = dateStr;
        titleEl.textContent = 'Day Details';
        sectionsEl.innerHTML = '';

        if (Array.isArray(classes) && classes.length) {
            const list = classes
                .map((c) => (
                    `<div class="p-3 rounded-xl bg-slate-50/50 border border-slate-100">
                        <div class="flex items-start justify-between gap-3">
                            <div>
                                <p class="text-sm font-semibold text-slate-900">${esc(c.subject)}</p>
                                <p class="text-xs text-slate-500 mt-1">${esc(c.room)} - ${esc(c.instructor)}</p>
                            </div>
                            <span class="minimal-badge bg-slate-100 text-slate-700">${esc(c.start_time)}-${esc(c.end_time)}</span>
                        </div>
                    </div>`
                ))
                .join('');
            sectionsEl.appendChild(buildSection('Weekly Classes', `<div class="space-y-3">${list}</div>`));
        }

        if (Array.isArray(events) && events.length) {
            const list = events
                .map((e) => (
                    `<div class="p-3 rounded-xl bg-slate-50/50 border border-slate-100">
                        <p class="text-sm font-semibold text-slate-900">${esc(e.title)}</p>
                        <p class="text-xs text-slate-500 mt-1">${esc(e.location)} - ${esc(e.start_at)} -> ${esc(e.end_at)}</p>
                    </div>`
                ))
                .join('');
            sectionsEl.appendChild(buildSection('Scheduled Events', `<div class="space-y-3">${list}</div>`));
        }

        if (Array.isArray(items) && items.length) {
            const list = items
                .map((it) => {
                    const isHoliday = it.type === 'HOLIDAY';
                    const box = isHoliday
                        ? 'border-rose-200 bg-gradient-to-r from-rose-50 to-white'
                        : 'border-amber-200 bg-gradient-to-r from-amber-50 to-white';
                    const badge = isHoliday
                        ? 'bg-rose-100 text-rose-700'
                        : 'bg-amber-100 text-amber-700';
                    return `<div class="p-4 rounded-xl border ${box}">
                        <div class="flex items-start justify-between gap-3">
                            <div>
                                <span class="minimal-badge ${badge}">${esc(it.type)}</span>
                                <p class="text-sm font-semibold text-slate-900 mt-2">${esc(it.title)}</p>
                                <p class="text-sm text-slate-600 mt-1">${esc(it.description)}</p>
                            </div>
                        </div>
                    </div>`;
                })
                .join('');
            sectionsEl.appendChild(buildSection('Special / Holidays', `<div class="space-y-3">${list}</div>`));
        }

        if (!classes.length && (!events || !events.length) && (!items || !items.length)) {
            sectionsEl.appendChild(buildSection('Nothing scheduled', '<p class="text-sm text-slate-500">No classes, events, or holidays found for this date.</p>'));
        }
    }

    calendarRoot.querySelectorAll('[data-cal-date]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const dateStr = btn.dataset.calDate;
            const items = btn.dataset.items ? JSON.parse(btn.dataset.items) : [];
            const events = btn.dataset.events ? JSON.parse(btn.dataset.events) : [];
            renderForDate(dateStr, items, events);
            openSheet();
        });
    });

    closeBtn.addEventListener('click', closeSheet);
    backdrop.addEventListener('click', closeSheet);

    let startY = 0;
    let currentY = 0;
    let dragging = false;
    let dragRaf = 0;
    let pendingDelta = 0;

    function onStart(e) {
        dragging = true;
        startY = (e.touches ? e.touches[0].clientY : e.clientY);
        currentY = startY;
        sheet.style.transition = 'none';
        sheet.style.willChange = 'transform';
    }

    function onMove(e) {
        if (!dragging) {
            return;
        }
        if (e.cancelable) {
            e.preventDefault();
        }
        currentY = (e.touches ? e.touches[0].clientY : e.clientY);
        pendingDelta = Math.max(0, currentY - startY);
        if (dragRaf) {
            return;
        }
        dragRaf = window.requestAnimationFrame(() => {
            dragRaf = 0;
            sheet.style.transform = `translateY(${pendingDelta}px)`;
        });
    }

    function onEnd() {
        if (!dragging) {
            return;
        }
        dragging = false;
        if (dragRaf) {
            window.cancelAnimationFrame(dragRaf);
            dragRaf = 0;
        }
        const delta = Math.max(0, currentY - startY);
        sheet.style.transition = '';
        sheet.style.transform = '';
        sheet.style.willChange = '';
        if (delta > 120) {
            closeSheet();
        }
    }

    handleEl.addEventListener('touchstart', onStart, { passive: true });
    handleEl.addEventListener('touchmove', onMove, { passive: false });
    handleEl.addEventListener('touchend', onEnd);

    handleEl.addEventListener('mousedown', onStart);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onEnd);
}

function initMobileNav() {
    const toggles = Array.from(document.querySelectorAll('[data-mobile-nav-toggle]'));
    const drawer = document.querySelector('[data-mobile-nav-drawer]');
    const backdrop = document.querySelector('[data-mobile-nav-backdrop]');

    if (!toggles.length || !drawer || !backdrop) {
        return;
    }

    function setExpanded(value) {
        toggles.forEach((t) => t.setAttribute('aria-expanded', value ? 'true' : 'false'));
    }

    function open() {
        drawer.classList.remove('-translate-x-full');
        backdrop.classList.remove('opacity-0', 'pointer-events-none');
        backdrop.classList.add('opacity-100');
        setExpanded(true);
    }

    function close() {
        drawer.classList.add('-translate-x-full');
        backdrop.classList.add('opacity-0', 'pointer-events-none');
        backdrop.classList.remove('opacity-100');
        setExpanded(false);
    }

    function toggleMenu() {
        const isOpen = !drawer.classList.contains('-translate-x-full');
        if (isOpen) {
            close();
        } else {
            open();
        }
    }

    toggles.forEach((t) => t.addEventListener('click', toggleMenu));
    backdrop.addEventListener('click', close);

    drawer.querySelectorAll('a').forEach((a) => {
        a.addEventListener('click', close);
    });

    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            close();
        }
    });
}

function initVaultBottomSheet() {
    const actionBtn = document.getElementById('vaultActionBtn');
    const bottomSheet = document.getElementById('vaultBottomSheet');
    const backdrop = document.getElementById('vaultSheetBackdrop');
    const sheet = document.getElementById('vaultSheet');
    const closeBtn = document.getElementById('vaultSheetClose');
    const handle = document.getElementById('vaultSheetHandle');
    const createFolderTab = document.getElementById('createFolderTab');
    const uploadFileTab = document.getElementById('uploadFileTab');
    const createFolderContent = document.getElementById('createFolderContent');
    const uploadFileContent = document.getElementById('uploadFileContent');

    if (!actionBtn || !bottomSheet || !backdrop || !sheet || !closeBtn || !handle) {
        return;
    }

    let scrollLockY = 0;
    let currentTab = 0; // 0 = create folder, 1 = upload file

    function lockScroll() {
        scrollLockY = window.scrollY || 0;
        document.body.style.position = 'fixed';
        document.body.style.top = `-${scrollLockY}px`;
        document.body.style.left = '0';
        document.body.style.right = '0';
        document.body.style.width = '100%';
        document.body.style.overflow = 'hidden';
    }

    function unlockScroll() {
        document.body.style.position = '';
        const top = document.body.style.top;
        document.body.style.top = '';
        document.body.style.left = '';
        document.body.style.right = '';
        document.body.style.width = '';
        document.body.style.overflow = '';
        const y = top ? Math.abs(parseInt(top, 10)) : scrollLockY;
        window.scrollTo(0, Number.isFinite(y) ? y : 0);
    }

    function openSheet() {
        lockScroll();
        bottomSheet.classList.remove('opacity-0', 'pointer-events-none');
        bottomSheet.classList.add('opacity-100');
        sheet.classList.remove('translate-y-full');
        backdrop.classList.remove('pointer-events-none');
        backdrop.classList.add('pointer-events-auto');
    }

    function closeSheet() {
        bottomSheet.classList.add('opacity-0', 'pointer-events-none');
        bottomSheet.classList.remove('opacity-100');
        sheet.classList.add('translate-y-full');
        backdrop.classList.add('pointer-events-none');
        backdrop.classList.remove('pointer-events-auto');
        unlockScroll();
    }

    function switchTab(index) {
        currentTab = index;
        
        // Update tab buttons
        if (createFolderTab && uploadFileTab) {
            const isActive = index === 0;
            createFolderTab.classList.toggle('bg-white', isActive);
            createFolderTab.classList.toggle('text-slate-900', isActive);
            createFolderTab.classList.toggle('shadow-sm', isActive);
            createFolderTab.classList.toggle('text-slate-600', !isActive);
            
            uploadFileTab.classList.toggle('bg-white', !isActive);
            uploadFileTab.classList.toggle('text-slate-900', !isActive);
            uploadFileTab.classList.toggle('shadow-sm', !isActive);
            uploadFileTab.classList.toggle('text-slate-600', isActive);
        }
        
        // Update content
        if (createFolderContent && uploadFileContent) {
            createFolderContent.classList.toggle('hidden', currentTab !== 0);
            uploadFileContent.classList.toggle('hidden', currentTab !== 1);
        }
    }

    // Event listeners
    actionBtn.addEventListener('click', openSheet);
    closeBtn.addEventListener('click', closeSheet);
    backdrop.addEventListener('click', closeSheet);

    if (createFolderTab) {
        createFolderTab.addEventListener('click', () => switchTab(0));
    }
    
    if (uploadFileTab) {
        uploadFileTab.addEventListener('click', () => switchTab(1));
    }

    // Swipe gesture handling
    let startX = 0;
    let startY = 0;
    let isDragging = false;
    let dragStartTime = 0;

    function handleTouchStart(e) {
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
        isDragging = true;
        dragStartTime = Date.now();
    }

    function handleTouchMove(e) {
        if (!isDragging) return;
        
        const currentX = e.touches[0].clientX;
        const currentY = e.touches[0].clientY;
        const deltaX = currentX - startX;
        const deltaY = currentY - startY;
        
        // Check if it's a horizontal swipe (more horizontal than vertical)
        if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 30) {
            // Prevent vertical scrolling during horizontal swipe
            e.preventDefault();
        }
    }

    function handleTouchEnd(e) {
        if (!isDragging) return;
        
        const endX = e.changedTouches[0].clientX;
        const endY = e.changedTouches[0].clientY;
        const deltaX = endX - startX;
        const deltaY = endY - startY;
        const deltaTime = Date.now() - dragStartTime;
        
        // Check if it's a valid horizontal swipe
        if (Math.abs(deltaX) > 50 && Math.abs(deltaX) > Math.abs(deltaY) && deltaTime < 300) {
            if (deltaX > 0 && currentTab === 1) {
                // Swipe right - switch to create folder
                switchTab(0);
            } else if (deltaX < 0 && currentTab === 0) {
                // Swipe left - switch to upload file
                switchTab(1);
            }
        }
        
        isDragging = false;
    }

    // Add swipe listeners to the sheet content area
    const contentArea = sheet.querySelector('.px-6.pb-6');
    if (contentArea) {
        contentArea.addEventListener('touchstart', handleTouchStart, { passive: true });
        contentArea.addEventListener('touchmove', handleTouchMove, { passive: false });
        contentArea.addEventListener('touchend', handleTouchEnd, { passive: true });
    }

    // Handle sheet drag to close
    let dragStartY = 0;
    let currentDragY = 0;
    let isDraggingSheet = false;

    function handleSheetDragStart(e) {
        dragStartY = e.touches ? e.touches[0].clientY : e.clientY;
        currentDragY = dragStartY;
        isDraggingSheet = true;
        sheet.style.transition = 'none';
        sheet.style.willChange = 'transform';
    }

    function handleSheetDragMove(e) {
        if (!isDraggingSheet) return;
        if (e.cancelable) {
            e.preventDefault();
        }
        
        currentDragY = e.touches ? e.touches[0].clientY : e.clientY;
        const deltaY = Math.max(0, currentDragY - dragStartY);
        sheet.style.transform = `translateY(${deltaY}px)`;
    }

    function handleSheetDragEnd() {
        if (!isDraggingSheet) return;
        
        isDraggingSheet = false;
        sheet.style.transition = '';
        sheet.style.transform = '';
        sheet.style.willChange = '';
        
        const deltaY = Math.max(0, currentDragY - dragStartY);
        if (deltaY > 120) {
            closeSheet();
        }
    }

    handle.addEventListener('touchstart', handleSheetDragStart, { passive: true });
    handle.addEventListener('touchmove', handleSheetDragMove, { passive: false });
    handle.addEventListener('touchend', handleSheetDragEnd);

    handle.addEventListener('mousedown', handleSheetDragStart);
    window.addEventListener('mousemove', handleSheetDragMove);
    window.addEventListener('mouseup', handleSheetDragEnd);

    // Initialize first tab
    switchTab(0);
}

function initVaultPageBottomSheet() {
    const actionBtn = document.getElementById('vaultPageActionBtn');
    const bottomSheet = document.getElementById('vaultPageBottomSheet');
    const backdrop = document.getElementById('vaultPageSheetBackdrop');
    const sheet = document.getElementById('vaultPageSheet');
    const closeBtn = document.getElementById('vaultPageSheetClose');
    const handle = document.getElementById('vaultPageSheetHandle');
    const createFolderTab = document.getElementById('vaultPageCreateFolderTab');
    const uploadFileTab = document.getElementById('vaultPageUploadFileTab');
    const createFolderContent = document.getElementById('vaultPageCreateFolderContent');
    const uploadFileContent = document.getElementById('vaultPageUploadFileContent');

    if (!actionBtn || !bottomSheet || !backdrop || !sheet || !closeBtn || !handle) {
        return;
    }

    let scrollLockY = 0;
    let currentTab = 0;

    function lockScroll() {
        scrollLockY = window.scrollY || 0;
        document.body.style.position = 'fixed';
        document.body.style.top = `-${scrollLockY}px`;
        document.body.style.left = '0';
        document.body.style.right = '0';
        document.body.style.width = '100%';
        document.body.style.overflow = 'hidden';
    }

    function unlockScroll() {
        document.body.style.position = '';
        const top = document.body.style.top;
        document.body.style.top = '';
        document.body.style.left = '';
        document.body.style.right = '';
        document.body.style.width = '';
        document.body.style.overflow = '';
        const y = top ? Math.abs(parseInt(top, 10)) : scrollLockY;
        window.scrollTo(0, Number.isFinite(y) ? y : 0);
    }

    function openSheet() {
        lockScroll();
        bottomSheet.classList.remove('opacity-0', 'pointer-events-none');
        bottomSheet.classList.add('opacity-100');
        sheet.classList.remove('translate-y-full');
        backdrop.classList.remove('pointer-events-none');
        backdrop.classList.add('pointer-events-auto');
    }

    function closeSheet() {
        bottomSheet.classList.add('opacity-0', 'pointer-events-none');
        bottomSheet.classList.remove('opacity-100');
        sheet.classList.add('translate-y-full');
        backdrop.classList.add('pointer-events-none');
        backdrop.classList.remove('pointer-events-auto');
        unlockScroll();
    }

    function switchTab(index) {
        currentTab = index;
        if (createFolderTab && uploadFileTab) {
            const isActive = index === 0;
            createFolderTab.classList.toggle('bg-white', isActive);
            createFolderTab.classList.toggle('text-slate-900', isActive);
            createFolderTab.classList.toggle('shadow-sm', isActive);
            createFolderTab.classList.toggle('text-slate-600', !isActive);

            uploadFileTab.classList.toggle('bg-white', !isActive);
            uploadFileTab.classList.toggle('text-slate-900', !isActive);
            uploadFileTab.classList.toggle('shadow-sm', !isActive);
            uploadFileTab.classList.toggle('text-slate-600', isActive);
        }

        if (createFolderContent && uploadFileContent) {
            createFolderContent.classList.toggle('hidden', currentTab !== 0);
            uploadFileContent.classList.toggle('hidden', currentTab !== 1);
        }
    }

    actionBtn.addEventListener('click', openSheet);
    closeBtn.addEventListener('click', closeSheet);
    backdrop.addEventListener('click', closeSheet);

    if (createFolderTab) {
        createFolderTab.addEventListener('click', () => switchTab(0));
    }
    if (uploadFileTab) {
        uploadFileTab.addEventListener('click', () => switchTab(1));
    }

    let dragStartY = 0;
    let currentDragY = 0;
    let isDraggingSheet = false;

    function handleSheetDragStart(e) {
        dragStartY = e.touches ? e.touches[0].clientY : e.clientY;
        currentDragY = dragStartY;
        isDraggingSheet = true;
        sheet.style.transition = 'none';
        sheet.style.willChange = 'transform';
    }

    function handleSheetDragMove(e) {
        if (!isDraggingSheet) return;
        if (e.cancelable) {
            e.preventDefault();
        }
        currentDragY = e.touches ? e.touches[0].clientY : e.clientY;
        const deltaY = Math.max(0, currentDragY - dragStartY);
        sheet.style.transform = `translateY(${deltaY}px)`;
    }

    function handleSheetDragEnd() {
        if (!isDraggingSheet) return;
        isDraggingSheet = false;
        const deltaY = Math.max(0, currentDragY - dragStartY);
        sheet.style.transition = '';
        sheet.style.transform = '';
        sheet.style.willChange = '';
        if (deltaY > 120) {
            closeSheet();
        }
    }

    handle.addEventListener('touchstart', handleSheetDragStart, { passive: true });
    handle.addEventListener('touchmove', handleSheetDragMove, { passive: false });
    handle.addEventListener('touchend', handleSheetDragEnd);

    handle.addEventListener('mousedown', handleSheetDragStart);
    window.addEventListener('mousemove', handleSheetDragMove);
    window.addEventListener('mouseup', handleSheetDragEnd);

    switchTab(0);
}

function initVaultFileManager() {
    const input = document.getElementById('vaultSearch');
    const list = document.getElementById('vaultFileList');
    const totalEl = document.getElementById('vaultTotal');
    const visibleEl = document.getElementById('vaultVisible');

    if (!input || !list || !totalEl || !visibleEl) {
        return;
    }

    const bulkBar = document.getElementById('vaultBulkBar');
    const selectedCountEl = document.getElementById('vaultSelectedCount');
    const selectAll = document.getElementById('vaultSelectAll');
    const clearBtn = document.getElementById('vaultClearSelection');
    const bulkDeleteForm = document.getElementById('vaultBulkDeleteForm');
    const bulkMoveForm = document.getElementById('vaultBulkMoveForm');
    const bulkCopyForm = document.getElementById('vaultBulkCopyForm');

    const items = Array.from(list.querySelectorAll('[data-vault-file]'));
    totalEl.textContent = String(items.length);

    function getCheckboxes() {
        return Array.from(list.querySelectorAll('.vault-file-checkbox'));
    }

    function selectedIds() {
        return getCheckboxes()
            .filter((c) => c.checked)
            .map((c) => String(c.value || '').trim())
            .filter(Boolean);
    }

    function clearDynamicInputs(form) {
        if (!form) return;
        form.querySelectorAll('input[data-vault-dyn="1"]').forEach((el) => el.remove());
    }

    function fillBulkForm(form) {
        if (!form) return;
        clearDynamicInputs(form);
        selectedIds().forEach((id) => {
            const inp = document.createElement('input');
            inp.type = 'hidden';
            inp.name = 'file_ids';
            inp.value = id;
            inp.setAttribute('data-vault-dyn', '1');
            form.appendChild(inp);
        });
    }

    function updateSelectionUI() {
        const ids = selectedIds();
        if (selectedCountEl) {
            selectedCountEl.textContent = String(ids.length);
        }
        if (bulkBar) {
            bulkBar.classList.toggle('hidden', ids.length === 0);
        }
        if (selectAll) {
            const boxes = getCheckboxes();
            const all = boxes.length > 0 && boxes.every((c) => c.checked);
            const none = boxes.every((c) => !c.checked);
            selectAll.indeterminate = !all && !none;
            selectAll.checked = all;
        }
    }

    function applyFilter() {
        const q = (input.value || '').trim().toLowerCase();
        let visible = 0;
        items.forEach((el) => {
            const hay = String(el.dataset.searchText || '');
            const ok = !q || hay.includes(q);
            el.style.display = ok ? '' : 'none';
            if (ok) {
                visible += 1;
            }
        });
        visibleEl.textContent = String(visible);
    }

    input.addEventListener('input', applyFilter);
    applyFilter();

    list.addEventListener('change', (e) => {
        const target = e.target;
        if (!(target instanceof HTMLInputElement)) return;
        if (target.classList.contains('vault-file-checkbox')) {
            updateSelectionUI();
        }
    });

    if (selectAll) {
        selectAll.addEventListener('change', () => {
            const checked = !!selectAll.checked;
            getCheckboxes().forEach((c) => {
                c.checked = checked;
            });
            updateSelectionUI();
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            getCheckboxes().forEach((c) => {
                c.checked = false;
            });
            updateSelectionUI();
        });
    }

    function bindBulkForm(form) {
        if (!form) return;
        form.addEventListener('submit', () => fillBulkForm(form));
    }
    bindBulkForm(bulkDeleteForm);
    bindBulkForm(bulkMoveForm);
    bindBulkForm(bulkCopyForm);

    async function copyText(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
            return;
        }
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        ta.remove();
    }

    list.querySelectorAll('.vaultShareBtn').forEach((btn) => {
        btn.addEventListener('click', async () => {
            const row = btn.closest('[data-vault-file]');
            if (!row) return;
            const url = row.getAttribute('data-download-url') || '';
            const name = row.querySelector('p')?.textContent?.trim() || 'Vault file';
            const absUrl = new URL(url, window.location.origin).toString();
            try {
                if (navigator.share) {
                    await navigator.share({ title: name, text: name, url: absUrl });
                    return;
                }
            } catch {
                // fall through to copy
            }
            try {
                await copyText(absUrl);
                window.alert('Link copied');
            } catch {
                window.prompt('Copy link:', absUrl);
            }
        });
    });

    updateSelectionUI();
}

document.addEventListener('DOMContentLoaded', () => {
    initPageProgress();
    generateAttendance();
    applyAttendanceRings();
    initWeeklyTimetable();
    initScheduleCalendarSheet();
    initMobileNav();
    initVaultBottomSheet();
    initVaultPageBottomSheet();
    initVaultFileManager();
    initChangePasswordBottomSheet();
    initAdminChangePasswordBottomSheet();

    const subtitle = document.getElementById('headerSubtitle');
    if (subtitle && subtitle.dataset.autodate === 'true') {
        const today = new Date();
        const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        subtitle.textContent = today.toLocaleDateString('en-US', options);
    }
});
