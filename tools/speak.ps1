param([Parameter(Mandatory=$true)][string]$TextFile,[Parameter(Mandatory=$true)][string]$OutputFile,[string]$Gender="female")
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Speech
$synth=New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
 $voices=$synth.GetInstalledVoices() | Where-Object {$_.Enabled -and $_.VoiceInfo.Culture.Name -eq 'zh-TW'}
 if(-not $voices){throw '未安裝繁體中文語音，請先在 Windows 安裝 zh-TW 文字轉語音。'}
 $preferred=$voices | Where-Object {$_.VoiceInfo.Gender.ToString().ToLower() -eq $Gender.ToLower()}
 if(-not $preferred){throw "未安裝 zh-TW $Gender 語音；不會改用其他性別。請安裝對應中文語音。"}
 $preferredName=if($Gender.ToLower() -eq 'male'){'Microsoft Zhiwei'}else{'Microsoft Yating'}
 $chosen=@($preferred | Where-Object {$_.VoiceInfo.Name -eq $preferredName})
 if(-not $chosen){$chosen=@($preferred)}
 $synth.SelectVoice($chosen[0].VoiceInfo.Name)
 $synth.Rate=0
 $synth.SetOutputToWaveFile($OutputFile)
 $synth.Speak([System.IO.File]::ReadAllText($TextFile,[System.Text.Encoding]::UTF8))
 $synth.SetOutputToNull()
 @{name=$synth.Voice.Name;gender=$synth.Voice.Gender.ToString().ToLower();locale=$synth.Voice.Culture.Name;engine='Windows System.Speech';policy='gender-strict-5.3.1'} | ConvertTo-Json | Set-Content -LiteralPath ($OutputFile+'.voice.json') -Encoding UTF8
} finally {$synth.Dispose()}
