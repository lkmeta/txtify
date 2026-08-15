// History table: client-side stats/filter + sort + pagination + delete. All
// rows are already on the page (retention keeps the count bounded), so this is
// cheap DOM work.
(function () {
    const table = document.getElementById('historyTable');
    if (!table) return;
    const tbody = table.querySelector('tbody');
    const PER_PAGE = 10;
    const colCount = table.querySelectorAll('thead th').length;
    let master = Array.from(tbody.querySelectorAll('tr'));  // every row, unfiltered
    let filter = 'all';
    let page = 1;
    let sort = { index: 1, type: 'number', asc: false };  // default: When, newest first

    const byId = id => document.getElementById(id);
    const cellValue = cell => cell.dataset.sortValue !== undefined ? cell.dataset.sortValue : cell.textContent.trim();

    function visibleRows() {
        const rows = filter === 'all' ? master.slice() : master.filter(r => r.dataset.status === filter);
        const { index, type, asc } = sort;
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
        return rows;
    }

    function fillerRow(text) {
        const tr = document.createElement('tr');
        tr.className = 'filler-row';
        const td = document.createElement('td');
        td.colSpan = colCount;
        if (text) { td.textContent = text; td.style.textAlign = 'center'; td.style.opacity = '.7'; }
        else { td.innerHTML = '&nbsp;'; }
        tr.appendChild(td);
        return tr;
    }

    function render() {
        const rows = visibleRows();
        const pages = Math.max(1, Math.ceil(rows.length / PER_PAGE));
        page = Math.min(Math.max(1, page), pages);

        // Always render exactly PER_PAGE row-slots so the table's height never
        // changes — short pages/filters are padded with empty rows.
        const nodes = rows.length === 0
            ? [fillerRow('No jobs match this filter.')]
            : rows.slice((page - 1) * PER_PAGE, page * PER_PAGE);
        while (nodes.length < PER_PAGE) nodes.push(fillerRow());
        tbody.replaceChildren(...nodes);

        // Stats always reflect the full set, not the current filter.
        const count = c => master.filter(r => r.dataset.status === c).length;
        byId('statTotal').textContent = master.length;
        byId('statSuccess').textContent = count('success');
        byId('statError').textContent = count('error');
        byId('statCanceled').textContent = count('canceled');

        byId('pageInfo').textContent = `Page ${page} of ${pages}`;
        byId('prevPage').disabled = page <= 1;
        byId('nextPage').disabled = page >= pages;
    }

    // Sorting
    table.querySelectorAll('th.sortable').forEach((th, i, all) => {
        th.addEventListener('click', () => {
            const index = Array.from(th.parentNode.children).indexOf(th);
            // toggle direction on the same column; new column starts ascending
            sort = { index, type: th.dataset.type || 'text', asc: sort.index === index ? !sort.asc : true };
            all.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
            th.classList.add(sort.asc ? 'sort-asc' : 'sort-desc');
            page = 1;
            render();
        });
    });

    // Filtering via the stat cards
    document.querySelectorAll('.stat').forEach(card => {
        card.addEventListener('click', () => {
            filter = card.dataset.filter;
            document.querySelectorAll('.stat').forEach(c => c.classList.toggle('active', c === card));
            page = 1;
            render();
        });
    });

    // Pagination
    byId('prevPage').addEventListener('click', () => { page--; render(); });
    byId('nextPage').addEventListener('click', () => { page++; render(); });

    // Delete
    window.deleteJob = function (id) {
        if (!confirm(`Delete job #${id} and its files? This cannot be undone.`)) return;
        fetch(`/history/delete?pid=${id}`, { method: 'POST' }).then(r => {
            if (r.ok) {
                master = master.filter(row => row.dataset.jobId != id);
                render();
            } else {
                r.json().then(d => alert(d.message || 'Could not delete the job.')).catch(() => alert('Could not delete the job.'));
            }
        }).catch(() => alert('Could not delete the job.'));
    };

    window.retryJob = function (id) {
        if (!confirm(`Re-run job #${id} with the same settings?`)) return;
        fetch(`/history/retry?pid=${id}`, { method: 'POST' }).then(r => {
            if (r.ok) {
                location.reload();  // the new job shows up (Processing)
            } else {
                r.json().then(d => alert(d.message || 'Could not retry the job.')).catch(() => alert('Could not retry the job.'));
            }
        }).catch(() => alert('Could not retry the job.'));
    };

    window.clearHistory = function () {
        if (!confirm('Delete ALL finished jobs and their files? This cannot be undone. (Running jobs are kept.)')) return;
        fetch('/history/clear', { method: 'POST' }).then(() => location.reload()).catch(() => alert('Could not clear history.'));
    };

    render();
})();
