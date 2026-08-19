(function () {
    const currentId = window.currentVersionId;
    const compareSelect = document.getElementById("compare_version");
    const resultsBody = document.getElementById("results-body");
    const resultsContainer = document.getElementById("results-container");
    const summaryCards = document.getElementById("summary-cards");
    const filtersDiv = document.getElementById("filters");
    const searchInput = document.getElementById("search-input");
    const categoryFilter = document.getElementById("category-filter");
    const locationFilter = document.getElementById("location-filter");
    const tableHeaders = document.querySelectorAll(".sortable-th");

    if (!compareSelect) return;

    let allRows = [];
    let sortCol = "diff";
    let sortDir = "desc";
    let summaryFilter = null;

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    function sortRows(rows) {
        const sorted = rows.slice().sort((a, b) => {
            let av = a[sortCol];
            let bv = b[sortCol];
            if (sortCol === "product_name" || sortCol === "location") {
                av = (av || "").toLowerCase();
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

    function matchesSummaryFilter(r) {
        if (!summaryFilter) return true;
        switch (summaryFilter) {
            case "increased":
                return r.diff !== null && r.diff !== undefined && r.diff > 0;
            case "decreased":
                return r.diff !== null && r.diff !== undefined && r.diff < 0;
            case "unchanged":
                return r.diff !== null && r.diff !== undefined && r.diff === 0;
            case "missing":
                return r.diff === null || r.diff === undefined;
            default:
                return true;
        }
    }

    function getDisplayRows() {
        const search = searchInput.value.toLowerCase().trim();
        const cat = categoryFilter.value.toLowerCase().trim();
        const loc = locationFilter.value.trim().toUpperCase();
        let filtered = allRows.filter(r => {
            if (search && !r.product_name.toLowerCase().includes(search) && !(r.product_category || "").toLowerCase().includes(search)) return false;
            if (cat && !(r.product_category || "").toLowerCase().includes(cat)) return false;
            if (loc && r.location !== loc) return false;
            if (!matchesSummaryFilter(r)) return false;
            return true;
        });
        filtered = sortRows(filtered);
        return filtered;
    }

    function renderTable(rows) {
        resultsBody.innerHTML = "";
        if (!rows.length) {
            resultsBody.innerHTML = "<tr><td colspan='8' class='text-center'>No records found.</td></tr>";
            return;
        }
        rows.forEach(function (r) {
            const tr = document.createElement("tr");
            let diffClass = "diff-neutral";
            let diffText = "-";
            let pctText = "-";
            if (r.diff !== null && r.diff !== undefined) {
                diffText = (r.diff > 0 ? "+" : "") + Number(r.diff).toFixed(2);
                diffClass = r.diff > 0 ? "diff-positive" : (r.diff < 0 ? "diff-negative" : "diff-neutral");
            }
            if (r.diff_pct !== null && r.diff_pct !== undefined) {
                pctText = (r.diff_pct > 0 ? "+" : "") + Number(r.diff_pct).toFixed(2) + "%";
            }
            tr.innerHTML = `
                <td>${escapeHtml(r.product_name)}</td>
                <td class="col-category">${escapeHtml(r.product_category || "-")}</td>
                <td class="col-unit">${escapeHtml(r.unit || "-")}</td>
                <td>${escapeHtml(r.location)}</td>
                <td>${r.current_cost !== null && r.current_cost !== undefined ? Number(r.current_cost).toFixed(2) : "-"}</td>
                <td>${r.compared_cost !== null && r.compared_cost !== undefined ? Number(r.compared_cost).toFixed(2) : "-"}</td>
                <td class="${diffClass}">${diffText}</td>
                <td class="${diffClass}">${pctText}</td>
            `;
            resultsBody.appendChild(tr);
        });
    }

    function refreshView() {
        const rows = getDisplayRows();
        renderTable(rows);
        updateSortIndicators();
        updateSummaryCardActiveState();
    }

    function updateSummaryCardActiveState() {
        document.querySelectorAll(".summary-clickable").forEach(card => {
            const filter = card.getAttribute("data-filter");
            if (summaryFilter === filter) {
                card.classList.add("active");
            } else {
                card.classList.remove("active");
            }
        });
    }

    function updateSummary(summary) {
        document.getElementById("sum-total").textContent = summary.total;
        document.getElementById("sum-increased").textContent = summary.increased;
        document.getElementById("sum-decreased").textContent = summary.decreased;
        document.getElementById("sum-unchanged").textContent = summary.unchanged;
        document.getElementById("sum-missing").textContent = summary.missing;
        document.getElementById("sum-hi").textContent = summary.highest_increase !== null ? (summary.highest_increase > 0 ? "+" : "") + Number(summary.highest_increase).toFixed(2) + "%" : "-";
        document.getElementById("sum-hd").textContent = summary.highest_decrease !== null ? (summary.highest_decrease > 0 ? "+" : "") + Number(summary.highest_decrease).toFixed(2) + "%" : "-";

        const diffs = allRows.map(r => r.diff).filter(v => v !== null && v !== undefined);
        const avgDiff = diffs.length ? diffs.reduce((a, b) => a + b, 0) / diffs.length : null;
        document.getElementById("sum-avg-diff").textContent = avgDiff !== null ? (avgDiff > 0 ? "+" : "") + Number(avgDiff).toFixed(2) : "-";
    }

    function populateCategories(rows) {
        const cats = Array.from(new Set(rows.map(r => r.product_category).filter(Boolean))).sort();
        categoryFilter.innerHTML = '<option value="">All Categories</option>';
        cats.forEach(c => {
            const opt = document.createElement("option");
            opt.value = c;
            opt.textContent = c;
            categoryFilter.appendChild(opt);
        });
    }

    async function loadComparison() {
        const compareId = compareSelect.value;
        if (!compareId) {
            resultsContainer.style.display = "none";
            summaryCards.style.display = "none";
            filtersDiv.style.display = "none";
            allRows = [];
            summaryFilter = null;
            document.getElementById("summary-hint").style.display = "none";
            return;
        }

        let url = `/api/compare?current_id=${currentId}`;
        if (compareId) {
            url += `&compare_id=${compareId}`;
        }

        try {
            const res = await fetch(url);
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                alert(err.error || "Failed to load comparison data.");
                return;
            }
            const data = await res.json();
            allRows = data.rows || [];
            sortCol = "diff";
            sortDir = "desc";
            summaryFilter = null;
            populateCategories(allRows);
            updateSummary(data.summary || {});
            refreshView();
            renderTop20();
            resultsContainer.style.display = "block";
            summaryCards.style.display = "grid";
            filtersDiv.style.display = "flex";
            document.getElementById("summary-hint").style.display = "block";
        } catch (e) {
            alert("Error loading comparison: " + e.message);
        }
    }

    function buildExportUrl() {
        const compareId = compareSelect.value;
        if (!compareId) return null;

        const params = new URLSearchParams();
        params.set("current_id", currentId);
        if (compareId) {
            params.set("compare_id", compareId);
        }
        const search = searchInput.value.trim();
        if (search) params.set("search", search);
        const cat = categoryFilter.value;
        if (cat) params.set("category", cat);
        const loc = locationFilter.value;
        if (loc) params.set("location", loc);
        if (summaryFilter) params.set("summary_filter", summaryFilter);
        return `/api/export?${params.toString()}`;
    }

    const downloadBtn = document.getElementById("download-report");
    if (downloadBtn) {
        downloadBtn.addEventListener("click", () => {
            const url = buildExportUrl();
            if (!url) {
                alert("Please select a comparison version first.");
                return;
            }
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
                sortDir = col === "product_name" || col === "location" ? "asc" : "desc";
            }
            refreshView();
        });
    });

    document.querySelectorAll(".summary-clickable").forEach(card => {
        card.addEventListener("click", () => {
            const filter = card.getAttribute("data-filter");
            if (summaryFilter === filter) {
                summaryFilter = null;
            } else {
                summaryFilter = filter;
            }
            refreshView();
        });
    });

    const top20Section = document.getElementById("top20-section");
    const top20Body = document.getElementById("top20-body");
    const toggleTop20Btn = document.getElementById("toggle-top20");

    function renderTop20() {
        if (!top20Body || !top20Section) return;
        const rowsWithDiff = allRows.filter(r => r.diff !== null && r.diff !== undefined);
        rowsWithDiff.sort((a, b) => Math.abs(b.diff) - Math.abs(a.diff));
        const topRows = rowsWithDiff.slice(0, 20);

        top20Body.innerHTML = "";
        if (!topRows.length) {
            top20Body.innerHTML = "<tr><td colspan='8' class='text-center'>No data available.</td></tr>";
            return;
        }
        topRows.forEach(function (r) {
            const tr = document.createElement("tr");
            let diffClass = "diff-neutral";
            let diffText = "-";
            let pctText = "-";
            if (r.diff !== null && r.diff !== undefined) {
                diffText = (r.diff > 0 ? "+" : "") + Number(r.diff).toFixed(2);
                diffClass = r.diff > 0 ? "diff-positive" : (r.diff < 0 ? "diff-negative" : "diff-neutral");
            }
            if (r.diff_pct !== null && r.diff_pct !== undefined) {
                pctText = (r.diff_pct > 0 ? "+" : "") + Number(r.diff_pct).toFixed(2) + "%";
            }
            tr.innerHTML = `
                <td>${escapeHtml(r.location)}</td>
                <td>${escapeHtml(r.product_category || "-")}</td>
                <td>${escapeHtml(r.product_name)}</td>
                <td>${escapeHtml(r.unit || "-")}</td>
                <td>${r.current_cost !== null && r.current_cost !== undefined ? Number(r.current_cost).toFixed(2) : "-"}</td>
                <td>${r.compared_cost !== null && r.compared_cost !== undefined ? Number(r.compared_cost).toFixed(2) : "-"}</td>
                <td class="${diffClass}">${diffText}</td>
                <td class="${diffClass}">${pctText}</td>
            `;
            top20Body.appendChild(tr);
        });
        top20Section.style.display = "block";
        if (toggleTop20Btn) toggleTop20Btn.textContent = "Hide";
    }

    if (toggleTop20Btn) {
        toggleTop20Btn.addEventListener("click", () => {
            if (top20Section.style.display === "none") {
                top20Section.style.display = "block";
                toggleTop20Btn.textContent = "Hide";
            } else {
                top20Section.style.display = "none";
                toggleTop20Btn.textContent = "Show";
            }
        });
    }

    searchInput.addEventListener("input", refreshView);
    categoryFilter.addEventListener("change", refreshView);
    locationFilter.addEventListener("change", refreshView);
    compareSelect.addEventListener("change", loadComparison);
})();
