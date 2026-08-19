(function () {
    const versionId = window.versionId;
    const searchInput = document.getElementById("search-input");
    const categoryFilter = document.getElementById("category-filter");
    const resultsBody = document.getElementById("results-body");
    const locations = window.locations || [];

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    function renderTable(matrixRows) {
        resultsBody.innerHTML = "";
        const locs = window.locations || [];
        if (!matrixRows.length) {
            resultsBody.innerHTML = `<tr><td colspan="${3 + 1 + (locs.length * 2)}" class="text-center">No products found.</td></tr>`;
            return;
        }
        matrixRows.forEach(function (row) {
            const tr = document.createElement("tr");
            let cells = `<td>${escapeHtml(row.product_name)}</td>
                <td class="col-category">${escapeHtml(row.product_category || "-")}</td>
                <td class="col-unit">${escapeHtml(row.unit || "-")}</td>
                <td>${row.average !== null ? Number(row.average).toFixed(2) : "-"}</td>`;
            locs.forEach(loc => {
                const cost = row.costs[loc];
                const dev = row.deviations[loc];
                cells += `<td>${cost !== null && cost !== undefined ? Number(cost).toFixed(2) : "-"}</td>`;
                cells += `<td>${dev !== null && dev !== undefined ? Number(dev).toFixed(2) : "-"}</td>`;
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
            renderTable(data.matrix_rows || []);

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

    searchInput.addEventListener("input", loadData);
    categoryFilter.addEventListener("change", loadData);

    loadData();
})();
