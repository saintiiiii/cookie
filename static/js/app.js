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
