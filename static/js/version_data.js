(function () {
    const versionId = window.versionId;
    const searchInput = document.getElementById("search-input");
    const categoryFilter = document.getElementById("category-filter");
    const locationFilter = document.getElementById("location-filter");
    const resultsBody = document.getElementById("results-body");

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    function renderTable(rows) {
        resultsBody.innerHTML = "";
        if (!rows.length) {
            resultsBody.innerHTML = "<tr><td colspan='5' class='text-center'>No records found.</td></tr>";
            return;
        }
        rows.forEach(function (r) {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${escapeHtml(r.product_name)}</td>
                <td class="col-category">${escapeHtml(r.product_category || "-")}</td>
                <td class="col-unit">${escapeHtml(r.unit || "-")}</td>
                <td>${escapeHtml(r.location)}</td>
                <td>${r.cost !== null && r.cost !== undefined ? Number(r.cost).toFixed(2) : "-"}</td>
            `;
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
        const loc = locationFilter.value;
        if (loc) params.set("location", loc);

        try {
            const res = await fetch(`/api/version-data?${params.toString()}`);
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                alert(err.error || "Failed to load data.");
                return;
            }
            const data = await res.json();
            renderTable(data.rows || []);

            if (categoryFilter.options.length <= 1 && data.categories) {
                data.categories.forEach(c => {
                    const opt = document.createElement("option");
                    opt.value = c;
                    opt.textContent = c;
                    categoryFilter.appendChild(opt);
                });
            }
        } catch (e) {
            alert("Error loading data: " + e.message);
        }
    }

    searchInput.addEventListener("input", loadData);
    categoryFilter.addEventListener("change", loadData);
    locationFilter.addEventListener("change", loadData);

    loadData();
})();
