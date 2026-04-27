document.addEventListener('DOMContentLoaded', () => {
    // Dark Mode Toggle Logic
    const themeToggle = document.getElementById('theme-toggle');
    const body = document.documentElement;
    const icon = themeToggle.querySelector('i');

    // Check saved theme
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        body.setAttribute('data-theme', 'dark');
        icon.classList.replace('fa-moon', 'fa-sun');
    }

    themeToggle.addEventListener('click', () => {
        if (body.getAttribute('data-theme') === 'dark') {
            body.removeAttribute('data-theme');
            localStorage.setItem('theme', 'light');
            icon.classList.replace('fa-sun', 'fa-moon');
        } else {
            body.setAttribute('data-theme', 'dark');
            localStorage.setItem('theme', 'dark');
            icon.classList.replace('fa-moon', 'fa-sun');
        }
        
        // Re-render charts on theme toggle to update text color
        if(typeof window.Chart !== 'undefined') {
            const fontColor = getComputedStyle(document.body).getPropertyValue('--text-color').trim();
            Chart.defaults.color = fontColor;
            for (let id in Chart.instances) {
                Chart.instances[id].update();
            }
        }
    });
});
