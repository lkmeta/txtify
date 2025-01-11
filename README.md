<div align="center">

<p align="center"> <img src="https://github.com/lkmeta/txtify/blob/main/static/Txtify.png" width="300px"></p>

<p><a href="https://txtify-web.vercel.app/">Demo Website</a> | <a href="https://www.youtube.com/watch?v=wha6_4zyXXo">Demo Video</a></p>

<hr class="custom-line">

[![](https://img.shields.io/github/license/lkmeta/txtify?colorB=ff0000)](https://github.com/lkmeta/txtify/blob/main/LICENSE)
[![](https://img.shields.io/badge/Open_Source-brightgreen.svg?colorB=ff0000)](https://github.com/lkmeta/Txtify)

</div>

<div align="center">
  <p>
    <img src="https://img.shields.io/badge/ASR-Whisper-1f425f.svg" alt="Whisper">
    <img src="https://img.shields.io/badge/%F0%9F%A4%97-Models-yellow" alt="Hugging Face">
    <img src="https://img.shields.io/badge/Translation-DeepL-1f425f.svg" alt="DeepL">
    <img src="https://img.shields.io/badge/FastAPI-1f425f.svg" alt="FastAPI">
    <img src="https://img.shields.io/badge/Python_3.10-1f425f.svg" alt="Python">

  </p>
</div>

Txtify is a free open-source web application that transcribes and translates audio from YouTube videos or uploaded media files. It now runs on Docker for easier deployment and includes monitoring capabilities. Leveraging the **`stable-ts`** library and the **`whisper`** models, Txtify offers enhanced transcription accuracy and performance.

## Table of Contents

- [About](#about)
- [Demo](#demo)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Roadmap](#roadmap)
- [Report Issues](#report-issues)
- [Contributing](#contributing)
- [License](#license)

## About

Txtify is designed to simplify the process of converting audio and video content into text. Whether you're looking to transcribe a YouTube video or your own audio/video files, Txtify offers an easy-to-use interface and powerful AI models to ensure accuracy and speed. The application supports multiple output formats including `.txt`, `.srt`, `.vtt`, and `.sbv`.

## Demo

<div align="center">

[![Txtify Demo Video](https://github.com/lkmeta/txtify/blob/main/static/Txtify_demo.png)](https://www.youtube.com/watch?v=wha6_4zyXXo)  
Check out the demo video to see Txtify in action.

</div>

## Prerequisites

Before you begin, ensure you have met the following requirements:

- Python 3.10 installed on your machine
- Docker (containerized deployment)
- An API key for DeepL if you want to enable translation (in case you need to use this tool for translation)

## Installation

To install and run Txtify using Docker, follow these steps:

1. Clone the repository:

```sh
git clone https://github.com/lkmeta/txtify.git
cd txtify
```

2. Set Up Environment Variables

```sh
cp .env.example .env
```

> <sub>Edit the .env file and add your DeepL API key for translation, and any other necessary environment variables.</sub>

3. Run the Docker

```sh
docker-compose up --build -d
```

> <sub>**Note:** The -d flag runs the container in detached mode.</sub>

4. Stop the Docker Container

```sh
docker-compose down
```

## Usage

### Access the Application

Open your web browser and navigate to `http://localhost:8010` to access Txtify.

### Monitoring

To monitor the application and the transcription processes:

1. Ensure you have completed the installation steps above.

2. You can view the logs of the running Docker container to monitor the application output.

```sh
docker logs -f txtify_container
```

> <sub>**Note:** The -f option follows the log output in real-time.</sub>

### Online Simulation Demo

To understand how Txtify works, you can use the online simulation demo. Visit [Txtify Website](https://txtify-web.vercel.app/) and follow the instructions to upload your media or enter a YouTube URL for a simulated transcription process.

## Roadmap

- [x] Basic transcription functionality
- [x] Support for multiple output formats
- [x] Integration with DeepL for translations
- [x] Improved UI/UX
- [x] Containerized the application
- [x] Enhance performance and scalability
- [ ] Web browser Whisper option

## Report Issues

If you encounter any issues, bugs, or have suggestions for improvements, please report them using one of the following methods:

- Contact Form: Visit our [Contact Page](https://txtify-web.vercel.app/contact) and submit your feedback or issue.
- GitHub Issues: Open an issue on the repository's issue tracker. Please provide detailed information to help us address the problem effectively.

> <sub>Your feedback is valuable and helps us improve Txtify!</sub>

## Contributing

Feel free to contribute by opening issues, suggesting improvements, or submitting pull requests. Your feedback is highly appreciated!

## License

This project is licensed under [Apache 2.0](https://github.com/lkmeta/Txtify/blob/main/LICENSE).
