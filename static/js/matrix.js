(function () {
    const versionId = window.versionId;
    const searchInput = document.getElementById("search-input");
    const categoryFilter = document.getElementById("category-filter");
    const resultsBody = document.getElementById("results-body");
    const locations = window.locations || [];
    const tableHeaders = document.querySelectorAll(".sortable-th");

    let currentRows = [];
    let sortCol = "product_name";
    let sortDir = "asc";

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    function sortRows(rows) {
        const sorted = rows.slice().sort((a, b) => {
            let av, bv;
            if (sortCol === "average") {
                av = a.average;
                bv = b.average;
            } else if (sortCol === "std_deviation") {
                av = a.std_deviation;
                bv = b.std_deviation;
            } else if (locations.includes(sortCol)) {
                av = a.costs ? a.costs[sortCol] : null;
                bv = b.costs ? b.costs[sortCol] : null;
            } else {
                av = a[sortCol];
                bv = b[sortCol];
            }

            if (typeof av === "string") {
                av = av.toLowerCase();
                bv = (bv || "").toLowerCase();
                if (av < bv) return sortDir === "asc" ? -1 : 1;
                if (av > bv) return sortDir === "asc" ? 1 : -1;
                return 0;
            }

            if (av === null || av === undefined) av = sortDir === "asc" ? Infinity : -Infinity;
            if (bv === null || bv === undefined) bv = sortDir === "asc" ? Infinity : -Infinity;
            if (av < bv) return sortDir === "asc" ? -1 : 1;
            if (av > bv) return sortDir === "asc" ? 1 : -1;
            return 0;
        });
        return sorted;
    }

    function updateSortIndicators() {
        tableHeaders.forEach(th => {
            const col = th.getAttribute("data-sort");
            const indicator = th.querySelector(".sort-indicator");
            if (!indicator) return;
            if (col === sortCol) {
                indicator.textContent = sortDir === "asc" ? " ▲" : " ▼";
            } else {
                indicator.textContent = "";
            }
        });
    }

    function renderTable(matrixRows) {
        resultsBody.innerHTML = "";
        const locs = window.locations || [];
        if (!matrixRows.length) {
            resultsBody.innerHTML = `<tr><td colspan="${5 + locs.length}" class="text-center">No products found.</td></tr>`;
            return;
        }
        const sorted = sortRows(matrixRows);
        sorted.forEach(function (row) {
            const tr = document.createElement("tr");
            let cells = `<td>${escapeHtml(row.product_name)}</td>
                <td class="col-category">${escapeHtml(row.product_category || "-")}</td>
                <td class="col-unit">${escapeHtml(row.unit || "-")}</td>
                <td>${row.average !== null ? Number(row.average).toFixed(2) : "-"}</td>
                <td>${row.std_deviation !== null && row.std_deviation !== undefined ? Number(row.std_deviation).toFixed(2) : "-"}</td>`;
            locs.forEach(loc => {
                const cost = row.costs[loc];
                cells += `<td>${cost !== null && cost !== undefined ? Number(cost).toFixed(2) : "-"}</td>`;
            });
            tr.innerHTML = cells;
            resultsBody.appendChild(tr);
        });
    }

    async function loadData() {
        const params = new URLSearchParams();
        params.set("version_id", versionId);
        const search = searchInput.value.trim();
        if (search) params.set("search", search);
        const cat = categoryFilter.value;
        if (cat) params.set("category", cat);

        try {
            const res = await fetch(`/api/matrix?${params.toString()}`);
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                alert(err.error || "Failed to load matrix data.");
                return;
            }
            const data = await res.json();
            currentRows = data.matrix_rows || [];
            renderTable(currentRows);
            updateSortIndicators();

            window.locations = data.locations || locations;
            if (categoryFilter.options.length <= 1 && data.categories) {
                data.categories.forEach(c => {
                    const opt = document.createElement("option");
                    opt.value = c;
                    opt.textContent = c;
                    categoryFilter.appendChild(opt);
                });
            }
        } catch (e) {
            alert("Error loading matrix: " + e.message);
        }
    }

    function buildExportUrl() {
        const params = new URLSearchParams();
        params.set("version_id", versionId);
        const search = searchInput.value.trim();
        if (search) params.set("search", search);
        const cat = categoryFilter.value;
        if (cat) params.set("category", cat);
        return `/api/export-matrix?${params.toString()}`;
    }

    const downloadBtn = document.getElementById("download-report");
    if (downloadBtn) {
        downloadBtn.addEventListener("click", () => {
            const url = buildExportUrl();
            window.location.href = url;
        });
    }

    tableHeaders.forEach(th => {
        th.addEventListener("click", () => {
            const col = th.getAttribute("data-sort");
            if (!col) return;
            if (sortCol === col) {
                sortDir = sortDir === "asc" ? "desc" : "asc";
            } else {
                sortCol = col;
                sortDir = "asc";
            }
            renderTable(currentRows);
            updateSortIndicators();
        });
    });

    searchInput.addEventListener("input", loadData);
    categoryFilter.addEventListener("change", loadData);

    loadData();
})();