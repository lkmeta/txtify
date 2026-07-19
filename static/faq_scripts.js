document.addEventListener('DOMContentLoaded', function () {
    fetchLanguagesFAQ('supported_languages_ASR.json', 'transcription-languages-list');
    fetchLanguagesFAQ('supported_languages_TR.json', 'translation-languages-list');
});

function fetchLanguagesFAQ(file, elementId) {
    fetch(`/static/${file}`)
        .then(response => response.json())
        .then(data => {
            let languages = [];
            if (file === 'supported_languages_ASR.json') {
                languages = Object.values(data.languages).map(lang => lang.name).filter(lang => lang !== 'Auto-Detect');
            } else {
                languages = Object.values(data.target_languages);
            }
            document.getElementById(elementId).innerText = languages.join(', ');
        })
        .catch(error => {
            console.error(`Error fetching ${file}:`, error);
        });
}


function toggleTheme() {
    document.body.classList.toggle('light-theme');
    document.body.classList.toggle('dark-theme');
    localStorage.setItem('theme', document.body.classList.contains('light-theme') ? 'light' : 'dark');
}

document.getElementById('themeToggle').addEventListener('change', toggleTheme);

// Apply the saved theme choice so it persists across pages and reloads
if (localStorage.getItem('theme') === 'light') {
    document.body.classList.replace('dark-theme', 'light-theme');
    document.getElementById('themeToggle').checked = true;
}

const menuToggle = document.getElementById('menuToggle');
const navLinks = document.getElementById('navLinks');
menuToggle.addEventListener('click', function () {
    const open = navLinks.classList.toggle('active');
    menuToggle.setAttribute('aria-expanded', open);
});

