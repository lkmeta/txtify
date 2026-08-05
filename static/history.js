// Client-side column sorting for the history table. The data is already on the
// page (retention keeps it small), so sorting is a cheap DOM reorder — no fetch.
(function () {
    const table = document.getElementById('historyTable');
    if (!table) return;
    const tbody = table.querySelector('tbody');

    function cellValue(cell) {
        // Prefer the raw sort value (epoch, seconds) over the displayed text.
        return cell.dataset.sortValue !== undefined ? cell.dataset.sortValue : cell.textContent.trim();
    }

    function sortBy(th) {
        const headers = Array.from(th.parentNode.children);
        const index = headers.indexOf(th);
        const type = th.dataset.type || 'text';
        // Toggle direction; default to ascending on a fresh column.
        const asc = !th.classList.contains('sort-asc');

        headers.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
        th.classList.add(asc ? 'sort-asc' : 'sort-desc');

        const rows = Array.from(tbody.querySelectorAll('tr'));
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
        rows.forEach(r => tbody.appendChild(r));
    }

    table.querySelectorAll('th.sortable').forEach(th => {
        th.addEventListener('click', () => sortBy(th));
    });
})();
