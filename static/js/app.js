const themeToggle = document.getElementById("themeToggle");

function syncThemeToggle() {
    if (!themeToggle) {
        return;
    }
    const isDark = document.documentElement.dataset.theme === "dark";
    themeToggle.innerHTML = isDark ? '<i class="bi bi-sun"></i>' : '<i class="bi bi-moon-stars"></i>';
    themeToggle.setAttribute("aria-label", isDark ? "Switch to light mode" : "Switch to dark mode");
    themeToggle.setAttribute("title", isDark ? "Switch to light mode" : "Switch to dark mode");
}

if (themeToggle) {
    syncThemeToggle();
    themeToggle.addEventListener("click", () => {
        const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
        document.documentElement.dataset.theme = nextTheme;
        localStorage.setItem("bakery-theme", nextTheme);
        syncThemeToggle();
    });
}

document.querySelectorAll("[data-submit-on-change]").forEach((element) => {
    element.addEventListener("change", () => element.closest("form")?.submit());
});

document.querySelectorAll("[data-password-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
        const input = document.getElementById(button.dataset.passwordToggle);
        if (!input) {
            return;
        }
        const isPassword = input.type === "password";
        input.type = isPassword ? "text" : "password";
        button.innerHTML = isPassword ? '<i class="bi bi-eye-slash"></i>' : '<i class="bi bi-eye"></i>';
    });
});

function passwordScore(value) {
    let score = 0;
    if (value.length >= 8) score += 1;
    if (/[A-Z]/.test(value)) score += 1;
    if (/[a-z]/.test(value)) score += 1;
    if (/[0-9]/.test(value)) score += 1;
    if (/[^A-Za-z0-9]/.test(value)) score += 1;
    return score;
}

document.querySelectorAll("[data-password-meter]").forEach((meter) => {
    const input = document.getElementById(meter.dataset.passwordMeter);
    const bar = meter.querySelector("span");
    const label = document.querySelector(`[data-password-label="${meter.dataset.passwordMeter}"]`);
    if (!input || !bar) {
        return;
    }
    input.addEventListener("input", () => {
        const score = passwordScore(input.value);
        const width = `${Math.max(score, input.value ? 1 : 0) * 20}%`;
        const text = score >= 5 ? "Strong" : score >= 3 ? "Medium" : input.value ? "Weak" : "Password strength";
        bar.style.width = width;
        meter.dataset.strength = score >= 5 ? "strong" : score >= 3 ? "medium" : "weak";
        if (label) {
            label.textContent = text;
        }
    });
});

document.querySelectorAll("[data-copy-target]").forEach((button) => {
    button.addEventListener("click", async () => {
        const input = document.getElementById(button.dataset.copyTarget);
        const status = document.querySelector(`[data-copy-status="${button.dataset.copyTarget}"]`);
        if (!input) {
            return;
        }
        input.select();
        input.setSelectionRange(0, input.value.length);
        try {
            await navigator.clipboard.writeText(input.value);
        } catch (_error) {
            document.execCommand("copy");
        }
        if (status) {
            status.textContent = "Copied.";
        }
        button.classList.add("btn-success");
        button.classList.remove("btn-primary");
        button.innerHTML = '<i class="bi bi-check2"></i><span>Copied</span>';
    });
});

const temporaryPasswordModal = document.getElementById("temporaryPasswordModal");
if (temporaryPasswordModal && temporaryPasswordModal.dataset.showTemporaryPassword === "true") {
    bootstrap.Modal.getOrCreateInstance(temporaryPasswordModal).show();
}

function readJsonScript(id, fallback) {
    const node = document.getElementById(id);
    if (!node) {
        return fallback;
    }
    try {
        return JSON.parse(node.textContent);
    } catch (_error) {
        return fallback;
    }
}

function formatMoney(value) {
    return `PHP ${Number(value || 0).toFixed(2)}`;
}

function toNumber(value, fallback = 0) {
    const number = Number.parseFloat(value);
    return Number.isFinite(number) ? number : fallback;
}

function createElement(tagName, options = {}) {
    const element = document.createElement(tagName);
    Object.entries(options).forEach(([key, value]) => {
        if (key === "className") {
            element.className = value;
        } else if (key === "text") {
            element.textContent = value;
        } else if (key === "dataset") {
            Object.assign(element.dataset, value);
        } else if (value !== null && value !== undefined) {
            element.setAttribute(key, value);
        }
    });
    return element;
}

function initPosForm() {
    const form = document.getElementById("posForm");
    if (!form) {
        return;
    }

    const products = readJsonScript("posProductData", []).map((product) => ({
        id: String(product.id),
        name: product.name,
        price: toNumber(product.price),
        barcode: product.barcode || "",
        sku: product.sku || "",
        stock: Number.parseInt(product.stock, 10) || 0,
    }));
    const productById = new Map(products.map((product) => [product.id, product]));
    const initialItems = readJsonScript("posInitialItems", [{ product_id: "", quantity: 1 }]);
    const rowsContainer = document.getElementById("posRows");
    const addButton = document.getElementById("addPosRow");
    const submitButton = document.getElementById("completeSaleButton");
    const barcodeLookup = document.getElementById("barcodeLookup");
    const barcodeFeedback = document.getElementById("barcodeFeedback");
    const discountType = document.getElementById("discountType");
    const promoDiscount = document.getElementById("promoDiscount");
    const taxRate = document.getElementById("taxRate");
    const paymentAmount = document.getElementById("paymentAmount");
    const status = document.getElementById("posStatus");
    const fields = {
        subtotal: document.getElementById("posSubtotal"),
        discount: document.getElementById("posDiscount"),
        tax: document.getElementById("posTax"),
        total: document.getElementById("posTotal"),
        change: document.getElementById("posChange"),
    };
    let rowCounter = 0;

    function setFieldError(input, message) {
        const feedbackId = input?.getAttribute("aria-describedby");
        const feedback = feedbackId ? document.getElementById(feedbackId.split(" ")[0]) : null;
        if (!input) {
            return;
        }
        input.classList.toggle("is-invalid", Boolean(message));
        input.setAttribute("aria-invalid", message ? "true" : "false");
        if (feedback) {
            feedback.textContent = message || "";
        }
    }

    function createProductSelect(rowId, selectedValue) {
        const select = createElement("select", {
            id: `posProduct${rowId}`,
            name: "product_id",
            className: "form-select pos-product",
            required: "",
            "aria-describedby": `posProduct${rowId}Feedback`,
        });
        select.appendChild(createElement("option", { value: "", text: "Choose product" }));
        products.forEach((product) => {
            const option = createElement("option", {
                value: product.id,
                text: `${product.name} | ${product.stock} in stock | ${product.barcode || product.sku}`,
                dataset: {
                    price: String(product.price),
                    barcode: product.barcode,
                    sku: product.sku,
                    stock: String(product.stock),
                },
            });
            if (String(selectedValue || "") === product.id) {
                option.selected = true;
            }
            select.appendChild(option);
        });
        return select;
    }

    function createRow(item = {}) {
        rowCounter += 1;
        const rowId = rowCounter;
        const row = createElement("div", { className: "row g-3 pos-row mb-2", dataset: { rowId: String(rowId) } });

        const productCol = createElement("div", { className: "col-md-6" });
        productCol.appendChild(createElement("label", {
            className: "form-label",
            for: `posProduct${rowId}`,
            text: "Product",
        }));
        productCol.appendChild(createProductSelect(rowId, item.product_id));
        productCol.appendChild(createElement("div", {
            className: "invalid-feedback",
            id: `posProduct${rowId}Feedback`,
        }));

        const quantityCol = createElement("div", { className: "col-md-2" });
        quantityCol.appendChild(createElement("label", {
            className: "form-label",
            for: `posQuantity${rowId}`,
            text: "Quantity",
        }));
        quantityCol.appendChild(createElement("input", {
            id: `posQuantity${rowId}`,
            name: "quantity",
            type: "number",
            min: "1",
            step: "1",
            value: item.quantity || "1",
            className: "form-control pos-quantity",
            required: "",
            inputmode: "numeric",
            "aria-describedby": `posQuantity${rowId}Feedback`,
        }));
        quantityCol.appendChild(createElement("div", {
            className: "invalid-feedback",
            id: `posQuantity${rowId}Feedback`,
        }));

        const lineCol = createElement("div", { className: "col-md-2 pos-line-total" });
        lineCol.appendChild(createElement("span", { className: "form-label", text: "Line Total" }));
        lineCol.appendChild(createElement("strong", { text: "PHP 0.00" }));

        const actionCol = createElement("div", { className: "col-md-2 d-flex align-items-end" });
        const removeButton = createElement("button", {
            type: "button",
            className: "btn btn-outline-danger w-100 remove-row",
            "aria-label": "Remove item",
        });
        removeButton.appendChild(createElement("i", { className: "bi bi-trash", "aria-hidden": "true" }));
        removeButton.appendChild(createElement("span", { className: "visually-hidden", text: "Remove" }));
        actionCol.appendChild(removeButton);

        row.append(productCol, quantityCol, lineCol, actionCol);
        return row;
    }

    function getRows() {
        return Array.from(rowsContainer.querySelectorAll(".pos-row"));
    }

    function getQuantity(input) {
        const quantity = Number.parseInt(input.value, 10);
        return Number.isFinite(quantity) ? quantity : 0;
    }

    function calculateAndValidate() {
        const rows = getRows();
        const requestedByProduct = new Map();
        const rowStates = [];
        let subtotal = 0;
        let hasErrors = false;

        rows.forEach((row) => {
            const productSelect = row.querySelector(".pos-product");
            const quantityInput = row.querySelector(".pos-quantity");
            const product = productById.get(productSelect.value);
            const quantity = getQuantity(quantityInput);
            if (product) {
                requestedByProduct.set(product.id, (requestedByProduct.get(product.id) || 0) + quantity);
                subtotal += product.price * quantity;
            }
            rowStates.push({ row, productSelect, quantityInput, product, quantity });
        });

        rowStates.forEach(({ row, productSelect, quantityInput, product, quantity }) => {
            const totalRequested = product ? requestedByProduct.get(product.id) : 0;
            const lineTotal = row.querySelector(".pos-line-total strong");
            setFieldError(productSelect, product ? "" : "Select a product.");
            if (!product) {
                hasErrors = true;
            }

            let quantityError = "";
            if (!Number.isInteger(quantity) || quantity < 1) {
                quantityError = "Enter a quantity of at least 1.";
            } else if (product && totalRequested > product.stock) {
                quantityError = `Only ${product.stock} in stock across all rows.`;
            }
            setFieldError(quantityInput, quantityError);
            hasErrors = hasErrors || Boolean(quantityError);
            if (lineTotal) {
                lineTotal.textContent = formatMoney(product ? product.price * quantity : 0);
            }
        });

        const promoValue = toNumber(promoDiscount.value);
        const taxValue = toNumber(taxRate.value, Number.NaN);
        let discount = 0;
        if (discountType.value === "senior" || discountType.value === "pwd") {
            discount = subtotal * 0.2;
        } else if (discountType.value === "promo") {
            discount = Math.min(Math.max(promoValue, 0), subtotal);
        }
        const taxable = Math.max(subtotal - discount, 0);
        const tax = taxable * (Number.isFinite(taxValue) ? taxValue : 0);
        const total = taxable + tax;
        const paid = toNumber(paymentAmount.value);
        const change = Math.max(paid - total, 0);

        setFieldError(promoDiscount, promoValue < 0 ? "Promo discount cannot be negative." : "");
        setFieldError(taxRate, !Number.isFinite(taxValue) || taxValue < 0 || taxValue > 1 ? "Tax rate must be between 0 and 1." : "");
        setFieldError(paymentAmount, paid < total ? `Payment must cover ${formatMoney(total)}.` : "");
        hasErrors = hasErrors || promoValue < 0 || !Number.isFinite(taxValue) || taxValue < 0 || taxValue > 1 || paid < total || rows.length === 0;

        fields.subtotal.textContent = formatMoney(subtotal);
        fields.discount.textContent = formatMoney(discount);
        fields.tax.textContent = formatMoney(tax);
        fields.total.textContent = formatMoney(total);
        fields.change.textContent = formatMoney(change);

        rows.forEach((row) => {
            const removeButton = row.querySelector(".remove-row");
            if (removeButton) {
                removeButton.disabled = rows.length <= 1;
            }
        });
        submitButton.disabled = hasErrors;
        status.textContent = hasErrors ? "Resolve the highlighted checkout issues before completing the sale." : "Sale is ready to complete.";
        return !hasErrors;
    }

    function addRow(item = {}) {
        rowsContainer.appendChild(createRow(item));
        calculateAndValidate();
    }

    function findProductByCode(code) {
        const normalized = code.trim().toLowerCase();
        return products.find((product) => (
            product.barcode.toLowerCase() === normalized || product.sku.toLowerCase() === normalized
        ));
    }

    function handleBarcodeSubmit(event) {
        if (event.key !== "Enter") {
            return;
        }
        event.preventDefault();
        const product = findProductByCode(barcodeLookup.value);
        if (!product) {
            barcodeLookup.classList.add("is-invalid");
            barcodeLookup.setAttribute("aria-invalid", "true");
            barcodeFeedback.textContent = "No matching active product was found.";
            return;
        }

        const matchingRow = getRows().find((row) => row.querySelector(".pos-product").value === product.id);
        const emptyRow = getRows().find((row) => !row.querySelector(".pos-product").value);
        const targetRow = matchingRow || emptyRow || (() => {
            addRow();
            const rows = getRows();
            return rows[rows.length - 1];
        })();
        const select = targetRow.querySelector(".pos-product");
        const quantity = targetRow.querySelector(".pos-quantity");
        select.value = product.id;
        quantity.value = matchingRow ? getQuantity(quantity) + 1 : Math.max(getQuantity(quantity), 1);
        barcodeLookup.value = "";
        barcodeLookup.classList.remove("is-invalid");
        barcodeLookup.setAttribute("aria-invalid", "false");
        barcodeFeedback.textContent = "";
        calculateAndValidate();
    }

    initialItems.forEach((item) => addRow(item));
    addButton.addEventListener("click", () => addRow());
    barcodeLookup.addEventListener("keydown", handleBarcodeSubmit);
    form.addEventListener("input", (event) => {
        if (event.target.matches(".pos-product, .pos-quantity, #discountType, #promoDiscount, #taxRate, #paymentAmount")) {
            calculateAndValidate();
        }
    });
    form.addEventListener("change", (event) => {
        if (event.target.matches(".pos-product, #discountType")) {
            calculateAndValidate();
        }
    });
    form.addEventListener("click", (event) => {
        const removeButton = event.target.closest(".remove-row");
        if (!removeButton || getRows().length <= 1) {
            return;
        }
        removeButton.closest(".pos-row").remove();
        calculateAndValidate();
    });
    form.addEventListener("submit", (event) => {
        if (!calculateAndValidate()) {
            event.preventDefault();
        }
    });
    calculateAndValidate();
}

initPosForm();
