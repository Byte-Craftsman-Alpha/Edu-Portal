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

document.addEventListener('DOMContentLoaded', () => {
    generateAttendance();
    applyAttendanceRings();
    initWeeklyTimetable();
    initScheduleCalendarSheet();
    initMobileNav();

    const subtitle = document.getElementById('headerSubtitle');
    if (subtitle && subtitle.dataset.autodate === 'true') {
        const today = new Date();
        const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        subtitle.textContent = today.toLocaleDateString('en-US', options);
    }
});
