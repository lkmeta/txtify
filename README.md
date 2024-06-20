<div align="center">

<p align="center"> <img src="https://github.com/lkmeta/txtify/blob/main/static/Txtify.png" width="300px"></p>

[![](https://img.shields.io/github/license/lkmeta/txtify?colorB=ff0000)](https://github.com/lkmeta/txtify/blob/main/LICENSE) 
[![](https://img.shields.io/badge/Open_Source-brightgreen.svg?colorB=ff0000)](https://github.com/lkmeta/Txtify)

</div>

<div align="center">
  <p>
    <img src="https://img.shields.io/badge/ASR-Whisper-1f425f.svg" alt="Whisper">
    <img src="https://img.shields.io/badge/ASR-SeamlessM4T-1f425f.svg" alt="SeamlessM4T">
    <img src="https://img.shields.io/badge/%F0%9F%A4%97-Models-yellow" alt="Hugging Face">
    <img src="https://img.shields.io/badge/Translation-DeepL-1f425f.svg" alt="DeepL">
    <img src="https://img.shields.io/badge/FastAPI-1f425f.svg" alt="FastAPI">
    <img src="https://img.shields.io/badge/Python_3.11-1f425f.svg" alt="Python">

  </p>
</div>


Txtify is a free and open-source web app for converting audio and video to text using advanced AI models. It supports YouTube videos and personal media files, offering fast and accurate transcriptions. Txtify can be self-hosted, giving you full control over your transcription process.

  
## Table of Contents

- [About](#about)
- [Demo](#demo)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
  - [Run Online Simulation Demo](#run-online-simulation-demo)
  - [Self Host](#self-host)
- [Roadmap](#roadmap)
- [Report Issues](#report-issues)
- [Contributing](#contributing)
- [License](#license)

## About

Txtify is designed to simplify the process of converting audio and video content into text. Whether you're looking to transcribe a YouTube video or your own audio/video files, Txtify offers an easy-to-use interface and powerful AI models to ensure accuracy and speed. The application supports multiple output formats including .txt, .pdf, .srt, .vtt, and .sbv.

## Demo


<div align="center">

[![Txtify Demo | Convert Audio and Video to Text using AI](https://markdown-videos-api.jorgenkh.no/url?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3Dwha6_4zyXXo)](https://www.youtube.com/watch?v=wha6_4zyXXo)

Check out the demo video to see Txtify in action.

</div>

## Prerequisites

Before you begin, ensure you have met the following requirements:

- Python 3.11 installed on your machine
- Conda installed on your machine (recommended to run on a conda environment)
- An API key for DeepL if you want to enable translation (in case you need to use this tool for translation)

## Installation

To install Txtify locally, follow these steps:

1. Clone the repository:
 ```sh
 git clone https://github.com/lkmeta/txtify.git
 cd txtify
 ```

2. Create a conda environment and activate it:

  ```sh
  conda create --name txtify python=3.11
  conda activate txtify
  ```

3. Install the dependencies:

```sh
pip install -r requirements.txt
```

## Usage

### Run Online Simulation Demo
You can use the online simulation demo of Txtify to understand how it works. Visit [Txtify Website](https://txtify-web.vercel.app/) and follow the instructions to upload your media or enter a YouTube URL for a simulated transcription process.

### Self Host

To self-host Txtify with full features, follow these steps:

1. Ensure you have completed the installation steps above.

2. Rename the .env.example file to .env and add your required DeepL API key for translation.

3. Start the server:
```sh
cd src/
python -m uvicorn main:app --reload --port 5000  --host "0.0.0.0"
```

4. Open your web browser and navigate to http://localhost:5000 and enjoy.

## Roadmap

- [x] Basic transcription functionality
- [x] Support for multiple output formats
- [x] Integration with DeepL for translations
- [x] Improved UI/UX
- [ ] Enhance performance and scalability
- [ ] Web browser Whisper option


## Report Issues

If you encounter any issues or have suggestions, please use the contact form on the [Contact Page](https://txtify-web.vercel.app/contact) to let us know.


## Contributing
Feel free to contribute by opening issues, suggesting improvements, or submitting pull requests. Your feedback is highly appreciated!

## License
This project is licensed under [Apache 2.0](https://github.com/lkmeta/Txtify/blob/main/LICENSE).
