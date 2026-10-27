# Txtify option values

Values accepted by Txtify's `/transcribe` form (taken from its source: `static/supported_languages_ASR.json` and `src/deepl_languages.py`).

## Spoken language (`language`): Whisper codes

| code | language |
|---|---|
| `auto` | Auto-Detect |
| `af` | Afrikaans |
| `am` | Amharic |
| `ar` | Arabic |
| `as` | Assamese |
| `az` | Azerbaijani |
| `be` | Belarusian |
| `bg` | Bulgarian |
| `bn` | Bengali |
| `bs` | Bosnian |
| `ca` | Catalan |
| `ceb` | Cebuano |
| `cs` | Czech |
| `cy` | Welsh |
| `da` | Danish |
| `de` | German |
| `el` | Greek |
| `en` | English |
| `es` | Spanish |
| `et` | Estonian |
| `fa` | Persian |
| `fi` | Finnish |
| `fr` | French |
| `gl` | Galician |
| `gu` | Gujarati |
| `he` | Hebrew |
| `hi` | Hindi |
| `hr` | Croatian |
| `hu` | Hungarian |
| `hy` | Armenian |
| `id` | Indonesian |
| `is` | Icelandic |
| `it` | Italian |
| `ja` | Japanese |
| `jv` | Javanese |
| `ka` | Georgian |
| `kk` | Kazakh |
| `km` | Khmer |
| `kn` | Kannada |
| `ko` | Korean |
| `lo` | Lao |
| `lt` | Lithuanian |
| `lv` | Latvian |
| `ml` | Malayalam |
| `mn` | Mongolian |
| `mr` | Marathi |
| `ms` | Malay |
| `my` | Burmese |
| `ne` | Nepali |
| `nl` | Dutch |
| `pa` | Punjabi |
| `pl` | Polish |
| `pt` | Portuguese |
| `ro` | Romanian |
| `ru` | Russian |
| `si` | Sinhala |
| `sk` | Slovak |
| `sl` | Slovenian |
| `sq` | Albanian |
| `sr` | Serbian |
| `sv` | Swedish |
| `sw` | Swahili |
| `ta` | Tamil |
| `te` | Telugu |
| `th` | Thai |
| `tr` | Turkish |
| `uk` | Ukrainian |
| `ur` | Urdu |
| `uz` | Uzbek |
| `vi` | Vietnamese |
| `yi` | Yiddish |
| `yo` | Yoruba |
| `zh` | Chinese |

## DeepL source languages

Translation needs the spoken language to be `auto` or one of these (the Whisper code, upper-cased, must match):

`AR` Arabic, `BG` Bulgarian, `CS` Czech, `DA` Danish, `DE` German, `EL` Greek, `EN` English, `ES` Spanish, `ET` Estonian, `FI` Finnish, `FR` French, `HU` Hungarian, `ID` Indonesian, `IT` Italian, `JA` Japanese, `KO` Korean, `LT` Lithuanian, `LV` Latvian, `NB` Norwegian Bokmål, `NL` Dutch, `PL` Polish, `PT` Portuguese, `RO` Romanian, `RU` Russian, `SK` Slovak, `SL` Slovenian, `SV` Swedish, `TR` Turkish, `UK` Ukrainian, `ZH` Chinese

## DeepL target languages (`language_translation`)

| code | language |
|---|---|
| `AR` | Arabic |
| `BG` | Bulgarian |
| `CS` | Czech |
| `DA` | Danish |
| `DE` | German |
| `EL` | Greek |
| `EN` | English |
| `EN-GB` | English (British) |
| `EN-US` | English (American) |
| `ES` | Spanish |
| `ET` | Estonian |
| `FI` | Finnish |
| `FR` | French |
| `HU` | Hungarian |
| `ID` | Indonesian |
| `IT` | Italian |
| `JA` | Japanese |
| `KO` | Korean |
| `LT` | Lithuanian |
| `LV` | Latvian |
| `NB` | Norwegian Bokmål |
| `NL` | Dutch |
| `PL` | Polish |
| `PT` | Portuguese |
| `PT-BR` | Portuguese (Brazilian) |
| `PT-PT` | Portuguese (excluding Brazilian Portuguese) |
| `RO` | Romanian |
| `RU` | Russian |
| `SK` | Slovak |
| `SL` | Slovenian |
| `SV` | Swedish |
| `TR` | Turkish |
| `UK` | Ukrainian |
| `ZH` | Chinese (simplified) |
