function showInput(type) {
    const youtubeInput = document.getElementById('youtube-input');
    const uploadInput = document.getElementById('upload-input');
    const youtubeButton = document.getElementById('youtube-button');
    const uploadButton = document.getElementById('upload-button');

    if (type === 'youtube') {
        youtubeInput.style.display = 'block';
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

    // Simulate transcription process
    simulateTranscription(sttModel, languageChoice, translation, languageTranslation, fileExport);
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

function simulateTranscription(model, language, translation, languageTranslation, fileExport) {
    let progress = 0;
    const interval = setInterval(() => {
        if (progress >= 100) {
            clearInterval(interval);
            document.getElementById('progressPhase').innerText = 'Completed';
        } else {
            progress += 10;
            document.getElementById('progressPercentage').innerText = `${progress}%`;
            document.getElementById('progressPhase').innerText = getPhase(progress);

            if (progress === 100) {
                // TODO


                // // Stop the rotation animation
                // document.getElementById('progressSpinner').style.animation = 'none';
                // document.getElementById('progressSpinner').offsetHeight; // Trigger reflow
                // document.getElementById('progressSpinner').style.animation = null;

                // // Show download button
                // document.getElementById('progressDownload').style.display = 'block';
                // // make downloadButton visible and clickable
                // document.getElementById('downloadButton').style.display = 'block';
                // // make downloadButton clickable
                // document.getElementById('downloadButton').href = 'static/transcription.txt';
            }
        }

        // Update stats
        document.getElementById('statsModel').innerHTML = `<span class="stat-title">Model:</span> ${model}`;
        document.getElementById('statsLanguage').innerHTML = `<span class="stat-title">Language:</span> ${language}`;
        document.getElementById('statsTranslation').innerHTML = `<span class="stat-title">Translation:</span> ${translation}`;
        document.getElementById('statsTime').innerHTML = `<span class="stat-title">Time Taken:</span> ${progress / 10}s`;
    }, 1000);
}

function getPhase(progress) {
    if (progress < 20) {
        return 'Uploading file...';
    } else if (progress < 40) {
        return 'Processing file...';
    } else if (progress < 60) {
        return 'Transcribing...';
    } else if (progress < 80) {
        return 'Translating...';
    } else {
        return 'Finalizing...';
    }
}

function cancelTranscription() {
    document.getElementById('progressOverlay').style.display = 'none';
}
