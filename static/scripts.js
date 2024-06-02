function showInput(type) {
    document.getElementById('youtube-input').style.display = type === 'youtube' ? 'block' : 'none';
    document.getElementById('upload-input').style.display = type === 'upload' ? 'block' : 'none';
    document.getElementById('youtube-button').classList.toggle('active', type === 'youtube');
    document.getElementById('upload-button').classList.toggle('active', type === 'upload');
}

function toggleTheme() {
    document.body.classList.toggle('light-theme');
    document.body.classList.toggle('dark-theme');
}

document.addEventListener('DOMContentLoaded', () => {
    const themeToggle = document.getElementById('themeToggle');
    themeToggle.addEventListener('change', toggleTheme);
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
        themeToggle.checked = true;
        document.body.classList.add('light-theme');
    } else {
        document.body.classList.add('dark-theme');
    }
});

function showAlert(title, message) {
    document.getElementById('alertTitle').innerText = title;
    document.getElementById('alertMessage').innerText = message;
    document.getElementById('alertOverlay').style.display = 'flex';
}

function closeAlert() {
    document.getElementById('alertOverlay').style.display = 'none';
}

function transcribe() {
    // This function will handle the transcribing process.
    showAlert('Transcription Started', 'Your transcription process has started. You will be notified when it is complete.');
}
