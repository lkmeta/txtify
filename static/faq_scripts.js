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

