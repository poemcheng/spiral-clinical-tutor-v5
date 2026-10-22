param([Parameter(Mandatory=$true)][string]$TextFile,[Parameter(Mandatory=$true)][string]$OutputFile,[string]$Gender="female")
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Speech
$synth=New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
 $voices=$synth.GetInstalledVoices() | Where-Object {$_.Enabled -and $_.VoiceInfo.Culture.Name -eq 'zh-TW'}
 if(-not $voices){throw '未安裝繁體中文語音，請先在 Windows 安裝 zh-TW 文字轉語音。'}
 $preferred=$voices | Where-Object {$_.VoiceInfo.Gender.ToString().ToLower() -eq $Gender.ToLower()}
 if($preferred){$synth.SelectVoice(@($preferred)[0].VoiceInfo.Name)}else{$synth.SelectVoice($voices[0].VoiceInfo.Name)}
 $synth.Rate=0
 $synth.SetOutputToWaveFile($OutputFile)
 $synth.Speak([System.IO.File]::ReadAllText($TextFile,[System.Text.Encoding]::UTF8))
} finally {$synth.Dispose()}
