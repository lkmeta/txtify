let transcriptionInterval;
let currentPid = null;  // Global variable to store the PID

function showInput(type) {
    const youtubeInput = document.getElementById('youtube-input');
    const uploadInput = document.getElementById('upload-input');
    const youtubeButton = document.getElementById('youtube-button');
    const uploadButton = document.getElementById('upload-button');

    if (type === 'youtube') {
        youtubeInput.style.display = 'flex';
        uploadInput.style.display = 'none';
        youtubeButton.classList.add('active');
        uploadButton.classList.remove('active');
    } else if (type === 'upload') {
        youtubeInput.style.display = 'none';
        uploadInput.style.display = 'block';
        youtubeButton.classList.remove('active');
        uploadButton.classList.add('active');
    }
}

function toggleTheme() {
    document.body.classList.toggle('light-theme');
    document.body.classList.toggle('dark-theme');
}

document.getElementById('themeToggle').addEventListener('change', toggleTheme);

function showAlert(title, message) {
    document.getElementById('alertTitle').innerText = title;
    document.getElementById('alertMessage').innerText = message;
    document.getElementById('alertOverlay').style.display = 'flex';
}

function closeAlert() {
    document.getElementById('alertOverlay').style.display = 'none';
}


function resetTranscription() {
    // Reset the progress overlay
    // document.getElementById('progressOverlay').style.display = 'none';
    document.getElementById('progressPercentage').innerText = '0%';
    document.getElementById('progressPhase').innerText = 'Downloading audio locally...Transcription will begin shortly.';

    // Reset the spinner color
    document.querySelector('.spinner').style.borderTop = '4px solid var(--text-color-dark)';

    // Reset the stats
    document.getElementById('statsModel').innerText = '';
    document.getElementById('statsLanguage').innerText = '';
    document.getElementById('statsTranslation').innerText = '';
    document.getElementById('statsTime').innerText = '';

    // Hide preview content and buttons
    document.getElementById('previewContent').classList.add('hidden');
    document.querySelector('.cancel-button').classList.add('hidden');
    document.querySelector('.download-button').classList.add('hidden');
    document.querySelector('.close-button').classList.add('hidden');

    // // Hide all preview tabs
    // document.getElementById('previewText').classList.add('hidden');
    // document.getElementById('previewSRT').classList.add('hidden');
    // document.getElementById('previewVTT').classList.add('hidden');
    // document.getElementById('previewSBV').classList.add('hidden');

    // Check if preview elements exist before setting innerText
    const previewText = document.getElementById('previewText');
    if (previewText) previewText.innerText = '';

    const previewSRT = document.getElementById('previewSRT');
    if (previewSRT) previewSRT.innerText = '';

    const previewVTT = document.getElementById('previewVTT');
    if (previewVTT) previewVTT.innerText = '';

    const previewSBV = document.getElementById('previewSBV');
    if (previewSBV) previewSBV.innerText = '';

    // Reset preview content
    document.getElementById('previewContainer').style.display = 'none';

    // Reset form inputs
    document.getElementById('youtube-url').value = '';
    document.getElementById('media-upload').value = '';
    document.getElementById('language-choice').value = 'en';
    document.getElementById('stt-model').value = 'whisper_base';
    document.getElementById('translation').value = 'deepl';
    document.getElementById('language-translation').value = 'EN';
    // document.getElementById('file-export').value = 'txt';

    // Reset currentPid variable
    currentPid = null;

    // Clear the transcription interval
    if (transcriptionInterval) {
        clearInterval(transcriptionInterval);
    }
}

function transcribe() {

    // Get form data
    const youtubeUrl = document.getElementById('youtube-url').value;
    const mediaUpload = document.getElementById('media-upload').files[0];
    const languageChoice = document.getElementById('language-choice').value;
    const sttModel = document.getElementById('stt-model').value;
    const translation = document.getElementById('translation').value;
    const languageTranslation = document.getElementById('language-translation').value;
    // const fileExport = document.getElementById('file-export').value;


    // Check if both fields are empty
    if (!youtubeUrl && !mediaUpload) {
        showAlert('Invalid Input', 'Please enter a YouTube URL or upload a media file.');
        return;
    }

    // Validate YouTube URL
    if (youtubeUrl && !isValidYoutubeUrl(youtubeUrl)) {
        showAlert('Invalid URL', 'Please enter a valid YouTube URL.');
        return;
    }

    // Validate file upload
    if (mediaUpload && !isValidMediaFile(mediaUpload)) {
        showAlert('Invalid File', 'Please upload a valid MP4 or MP3 file.');
        return;
    }

    // Show progress overlay
    document.getElementById('progressOverlay').style.display = 'flex';

    // Create FormData and append form data
    let formData = new FormData();
    formData.append('language', languageChoice);
    formData.append('model', sttModel);
    formData.append('translation', translation);
    formData.append('language_translation', languageTranslation);
    // formData.append('file_export', fileExport);

    if (youtubeUrl) {
        formData.append('youtube_url', youtubeUrl);
    } else if (mediaUpload) {
        formData.append('media', mediaUpload);
    }

    // Send request
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/transcribe', true);
    xhr.onload = function () {
        if (xhr.status === 200) {
            const response = JSON.parse(xhr.responseText);
            currentPid = response.pid;  // Store the PID
            startStatusCheck(currentPid);
        } else {
            showAlert('Error', 'Failed to transcribe the media.');
            document.getElementById('progressOverlay').style.display = 'none';
        }
    };
    xhr.send(formData);
}

function startStatusCheck(pid) {

    // Check if the PID is valid
    if (!pid) {
        showAlert('Error', 'Invalid Process. Please try again.');
        return;
    }

    transcriptionInterval = setInterval(() => {
        const xhr = new XMLHttpRequest();
        xhr.open('GET', `/status?pid=${pid}`, true);
        xhr.onload = function () {
            if (xhr.status === 200) {
                const response = JSON.parse(xhr.responseText);
                console.log(response);

                updateProgress(response.progress, response.phase, response.model, response.language, response.translation, response.time_taken);
                if (response.progress >= 100) {
                    clearInterval(transcriptionInterval);
                    document.getElementById('progressPhase').innerText = 'Completed successfully! Download your files below.';
                    // document.querySelector('.cancel-button').style.display = 'none';
                    document.querySelector('.cancel-button').classList.add('hidden');
                    document.querySelector('.download-button').classList.remove('hidden');
                    document.querySelector('.close-button').classList.remove('hidden');
                }
            } else {
                showAlert('Error', 'Failed to check the transcription status.');
                console.log(xhr.responseText);
            }
        };
        xhr.send();
    }, 5000);
}

function isValidYoutubeUrl(url) {
    const regex = /^(https?\:\/\/)?(www\.youtube\.com|youtu\.be)\/.+$/;
    return regex.test(url);
}

function isValidMediaFile(file) {
    const validExtensions = ['mp4', 'mp3'];
    const fileExtension = file.name.split('.').pop().toLowerCase();
    return validExtensions.includes(fileExtension);
}

function cancelTranscription() {
    clearInterval(transcriptionInterval);
    document.getElementById('progressOverlay').style.display = 'none';
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `/cancel?pid=${currentPid}`, true);
    xhr.onload = function () {
        if (xhr.status !== 200) {
            showAlert('Error', 'Failed to cancel the transcription.');
        } else {
            showAlert('Success', 'Transcription has been cancelled.');
        }
    };
    xhr.send();
}

document.getElementById('transcribeButton').addEventListener('click', transcribe);

function downloadFile() {
    const xhr = new XMLHttpRequest();
    xhr.open('GET', `/download?pid=${currentPid}`, true);
    xhr.responseType = 'blob';
    xhr.onload = function () {
        if (xhr.status === 200) {
            const url = window.URL.createObjectURL(xhr.response);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'transcription.txt';  // File name // TODO here
            document.body.appendChild(a);
            a.click();
            a.remove();
        } else {
            showAlert('Error', 'Failed to download the file.');
        }
    };
    xhr.send();
}

document.querySelector('.cancel-button').addEventListener('click', cancelTranscription);
document.querySelector('.download-button').addEventListener('click', downloadFile);
document.querySelector('.close-button').addEventListener('click', closeProgress);


// preview section
function updateProgress(progress, phase, model, language, translation, timeTaken) {
    document.getElementById('progressPercentage').innerText = `${progress}%`;
    document.getElementById('progressPhase').innerText = phase;
    document.getElementById('statsModel').innerHTML = `<span class="stat-title">Model:</span> ${model}`;
    document.getElementById('statsLanguage').innerHTML = `<span class="stat-title">Language:</span> ${language}`;
    document.getElementById('statsTranslation').innerHTML = `<span class="stat-title">Translation:</span> ${translation}`;
    document.getElementById('statsTime').innerHTML = `<span class="stat-title">Time Taken:</span> ${timeTaken} seconds`;


    // if "In Progress" then show "Time Taken: In Progress"
    if (timeTaken === 'In Progress') {
        document.getElementById('statsTime').innerHTML = `<span class="stat-title">Time Taken:</span> ${timeTaken}`;
    } else {
        document.getElementById('statsTime').innerHTML = `<span class="stat-title">Time Taken:</span> ${timeTaken} seconds`;
    }

    // If phase is not "Initializing..." then unhide the cancel button
    if (phase !== 'Initializing...') {
        document.querySelector('.cancel-button').classList.remove('hidden');
    }

    if (progress >= 100) {
        document.querySelector('.cancel-button').classList.add('hidden');
        document.querySelector('.download-button').classList.remove('hidden');
        document.querySelector('.close-button').classList.remove('hidden');
        document.getElementById('previewContainer').style.display = 'block';

        // Change .spinner variable: border-top: 4px solid var(--text-color-dark) to border-top: 4px solid var(--primary-color)
        document.querySelector('.spinner').style.borderTop = '4px solid var(--primary-color)';

        // Fetch the preview
        fetchPreview();
    }
}

function fetchPreview() {
    const xhr = new XMLHttpRequest();
    xhr.open('GET', `/preview?pid=${currentPid}`, true);
    xhr.onload = function () {
        if (xhr.status === 200) {
            const response = JSON.parse(xhr.responseText);
            document.getElementById('previewText').innerText = response.txt;
            document.getElementById('previewSRT').innerText = response.srt;
            document.getElementById('previewVTT').innerText = response.vtt;
            document.getElementById('previewSBV').innerText = response.sbv;

            // if previewContent is hidden, unhide it
            if (document.getElementById('previewContent').classList.contains('hidden')) {
                document.getElementById('previewContent').classList.remove('hidden');
            }

            // Show the text preview by default
            showPreview('txt'); // Show the text preview by default
        } else {
            showAlert('Error', 'Failed to fetch the preview.');
        }
    };
    xhr.send();
}

function showPreview(format) {
    // Hide all previews
    document.getElementById('previewText').classList.add('hidden');
    document.getElementById('previewSRT').classList.add('hidden');
    document.getElementById('previewVTT').classList.add('hidden');
    document.getElementById('previewSBV').classList.add('hidden');

    // Remove active class from all tab buttons
    const tabButtons = document.querySelectorAll('.tab-button');
    tabButtons.forEach(button => {
        button.classList.remove('active');
    });

    // Show the selected preview and set the active tab button
    switch (format) {
        case 'txt':
            document.getElementById('previewText').classList.remove('hidden');
            document.querySelector('.tab-button[onclick="showPreview(\'txt\')"]').classList.add('active');
            break;
        case 'srt':
            document.getElementById('previewSRT').classList.remove('hidden');
            document.querySelector('.tab-button[onclick="showPreview(\'srt\')"]').classList.add('active');
            break;
        case 'vtt':
            document.getElementById('previewVTT').classList.remove('hidden');
            document.querySelector('.tab-button[onclick="showPreview(\'vtt\')"]').classList.add('active');
            break;
        case 'sbv':
            document.getElementById('previewSBV').classList.remove('hidden');
            document.querySelector('.tab-button[onclick="showPreview(\'sbv\')"]').classList.add('active');
            break;
        default:
            console.error('Unsupported format:', format);
    }
}

function downloadCurrentPreview() {
    const activeTab = document.querySelector('.tab-button.active').innerText.toLowerCase();
    const xhr = new XMLHttpRequest();
    xhr.open('GET', `/downloadPreview?pid=${currentPid}&format=${activeTab}`, true);
    xhr.responseType = 'blob';
    xhr.onload = function () {
        if (xhr.status === 200) {
            const url = window.URL.createObjectURL(xhr.response);
            const a = document.createElement('a');
            a.href = url;
            a.download = `transcription.${activeTab}`;  // File name
            document.body.appendChild(a);
            a.click();
            a.remove();
        } else {
            showAlert('Error', 'Failed to download the file.');
        }
    };
    xhr.send();
}

let languagesData = {};
let selectedModel = 'whisper'; // Default model

document.addEventListener('DOMContentLoaded', function () {
    fetchLanguages();
    document.getElementById('stt-model').addEventListener('change', updateLanguageCodes);
    fetchTranslationLanguages();
});

function fetchLanguages() {
    fetch('/static/supported_languages_ASR.json')
        .then(response => response.json())
        .then(data => {
            languagesData = data.languages;
            populateLanguageDropdown();
        })
        .catch(error => {
            console.error('Error fetching languages:', error);
        });
}

function populateLanguageDropdown() {
    const languageChoice = document.getElementById('language-choice');

    // Clear existing options
    languageChoice.innerHTML = '';

    // Add languages to the dropdown
    for (const code in languagesData) {
        const option = document.createElement('option');
        option.value = languagesData[code].whisper_code; // Default to Whisper code
        option.textContent = languagesData[code].name;
        languageChoice.appendChild(option);
    }

    // Set English as default selected language
    languageChoice.value = 'en';
}

function updateLanguageCodes() {
    const languageChoice = document.getElementById('language-choice');
    const selectedModel = document.getElementById('stt-model').value;

    // Check if selected model contains 'whisper' to determine the language code
    const whisperModel = selectedModel.includes('whisper');

    // Update language codes in the dropdown
    for (const option of languageChoice.options) {
        const langCode = Object.keys(languagesData).find(code => languagesData[code].name === option.textContent);
        if (langCode) {
            option.value = whisperModel ? languagesData[langCode].whisper_code : languagesData[langCode].m4t_code;
        }
    }
}


function fetchTranslationLanguages() {
    fetch('/static/supported_languages_TR.json')
        .then(response => response.json())
        .then(data => {
            populateTranslationDropdown(data.target_languages);
        })
        .catch(error => {
            console.error('Error fetching translation languages:', error);
        });
}


function populateTranslationDropdown(languages) {
    const languageTranslation = document.getElementById('language-translation');

    // Clear existing options
    languageTranslation.innerHTML = '';

    // Add languages to the dropdown
    for (const code in languages) {
        const option = document.createElement('option');
        option.value = code;
        option.textContent = languages[code];
        languageTranslation.appendChild(option);
    }

    // Set default language
    languageTranslation.value = 'EN';
}

document.addEventListener('DOMContentLoaded', function () {
    const sttModel = document.getElementById('stt-model');
    const options = sttModel.options;

    for (let i = 0; i < options.length; i++) {
        if (options[i].innerText.includes('FREE')) {
            options[i].style.color = 'var(--green-color)';
        }
        if (options[i].innerText.includes('RECOMMENDED')) {
            options[i].style.color = 'var(--primary-color)';
        }
    }
});


document.addEventListener('DOMContentLoaded', function () {
    const translation = document.getElementById('translation');
    const options = translation.options;

    for (let i = 0; i < options.length; i++) {
        if (options[i].innerText.includes('FREE')) {
            options[i].style.color = 'var(--green-color)';
        }
        if (options[i].innerText.includes('RECOMMENDED')) {
            options[i].style.color = 'var(--primary-color)';
        }
    }
});


function closeProgress() {

    // Reset Transcription
    resetTranscription();

    document.getElementById('progressOverlay').style.display = 'none';
}