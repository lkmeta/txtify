document.getElementById('contact-form').addEventListener('submit', async function (event) {
    event.preventDefault();

    const form = document.getElementById('contact-form');
    const formData = new FormData(form);

    try {
        const response = await fetch('/submit_contact', {
            method: 'POST',
            body: formData
        });

        if (response.status === 200) {
            showAlert('Success', 'Your message has been sent successfully! We will get back to you soon.');
            form.reset();  // Reset the form after successful submission
        } else {
            const errorData = await response.json();
            showAlert('Error', errorData.message || 'Failed to send your message.');
        }
    } catch (error) {
        console.error('Error:', error);
        showAlert('Error', 'Failed to send your message.');
    }
});

function showAlert(title, message) {
    const alertTitle = document.getElementById('alertTitle');
    const alertMessage = document.getElementById('alertMessage');

    if (alertTitle && alertMessage) {
        alertTitle.innerText = title;
        alertMessage.innerText = message;
        document.getElementById('alertOverlay').style.display = 'flex';
    } else {
        console.error('Alert elements not found');
    }
}

function closeAlert() {
    document.getElementById('alertOverlay').style.display = 'none';
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

