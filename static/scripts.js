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

function transcribe() {
    const youtubeUrl = document.getElementById('youtube-url').value;
    const mediaUpload = document.getElementById('media-upload').files[0];
    const languageChoice = document.getElementById('language-choice').value;
    const sttModel = document.getElementById('stt-model').value;
    const translation = document.getElementById('translation').value;
    const languageTranslation = document.getElementById('language-translation').value;
    const fileExport = document.getElementById('file-export').value;

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
    formData.append('file_export', fileExport);

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
                    document.getElementById('progressPhase').innerText = 'Completed successfully! Download your file below.';
                    document.querySelector('.cancel-button').style.display = 'none';
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

function updateProgress(progress, phase, model, language, translation, timeTaken) {
    document.getElementById('progressPercentage').innerText = `${progress}%`;
    document.getElementById('progressPhase').innerText = phase;
    document.getElementById('statsModel').innerHTML = `<span class="stat-title">Model:</span> ${model}`;
    document.getElementById('statsLanguage').innerHTML = `<span class="stat-title">Language:</span> ${language}`;
    document.getElementById('statsTranslation').innerHTML = `<span class="stat-title">Translation:</span> ${translation}`;

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

    // If progress is 100% then hide the cancel button and unhide the download and close buttons
    if (progress >= 100) {
        document.querySelector('.cancel-button').style.display = 'none';
        document.querySelector('.download-button').classList.remove('hidden');
        document.querySelector('.close-button').classList.remove('hidden');
    }
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

function closeProgress() {
    document.getElementById('progressOverlay').style.display = 'none';
}

document.querySelector('.cancel-button').addEventListener('click', cancelTranscription);
document.querySelector('.download-button').addEventListener('click', downloadFile);
document.querySelector('.close-button').addEventListener('click', closeProgress);
