// History table: client-side sort + pagination + delete. All rows are already
// on the page (retention keeps the count bounded), so this is cheap DOM work.
(function () {
    const table = document.getElementById('historyTable');
    if (!table) return;
    const tbody = table.querySelector('tbody');
    const PER_PAGE = 10;
    let rows = Array.from(tbody.querySelectorAll('tr'));
    let page = 1;

    function pageCount() {
        return Math.max(1, Math.ceil(rows.length / PER_PAGE));
    }

    function render() {
        page = Math.min(Math.max(1, page), pageCount());
        tbody.replaceChildren(...rows.slice((page - 1) * PER_PAGE, page * PER_PAGE));
        const info = document.getElementById('pageInfo');
        if (info) info.textContent = `Page ${page} of ${pageCount()} · ${rows.length} job${rows.length === 1 ? '' : 's'}`;
        const prev = document.getElementById('prevPage');
        const next = document.getElementById('nextPage');
        if (prev) prev.disabled = page <= 1;
        if (next) next.disabled = page >= pageCount();
    }

    function cellValue(cell) {
        return cell.dataset.sortValue !== undefined ? cell.dataset.sortValue : cell.textContent.trim();
    }

    function sortBy(th) {
        const headers = Array.from(th.parentNode.children);
        const index = headers.indexOf(th);
        const type = th.dataset.type || 'text';
        const asc = !th.classList.contains('sort-asc');
        headers.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
        th.classList.add(asc ? 'sort-asc' : 'sort-desc');
        rows.sort((a, b) => {
            let av = cellValue(a.children[index]);
            let bv = cellValue(b.children[index]);
            if (type === 'number') {
                av = parseFloat(av) || 0;
                bv = parseFloat(bv) || 0;
                return asc ? av - bv : bv - av;
            }
            return asc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
        });
        page = 1;
        render();
    }

    table.querySelectorAll('th.sortable').forEach(th => th.addEventListener('click', () => sortBy(th)));
    const prev = document.getElementById('prevPage');
    const next = document.getElementById('nextPage');
    if (prev) prev.addEventListener('click', () => { page--; render(); });
    if (next) next.addEventListener('click', () => { page++; render(); });

    window.deleteJob = function (id) {
        if (!confirm(`Delete job #${id} and its files? This cannot be undone.`)) return;
        fetch(`/history/delete?pid=${id}`, { method: 'POST' }).then(r => {
            if (r.ok) {
                rows = rows.filter(row => row.dataset.jobId != id);
                render();
            } else {
                r.json().then(d => alert(d.message || 'Could not delete the job.')).catch(() => alert('Could not delete the job.'));
            }
        }).catch(() => alert('Could not delete the job.'));
    };

    window.clearHistory = function () {
        if (!confirm('Delete ALL finished jobs and their files? This cannot be undone. (Running jobs are kept.)')) return;
        fetch('/history/clear', { method: 'POST' }).then(() => location.reload()).catch(() => alert('Could not clear history.'));
    };

    render();
})();
