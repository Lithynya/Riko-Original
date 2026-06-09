from faster_whisper import WhisperModel
from process.asr_func.asr_auto_record import record_on_speech, transcribe_audio
from process.llm_funcs.llm_scr import llm_response
from process.tts_func.sovits_ping import sovits_gen, get_wav_duration
from process.tts_func.tts_preprocess import clean_llm_output
from process.vrm_func.vrm_ping import vrm_talk
from pathlib import Path
import os
import time
### transcribe audio 
import uuid
import soundfile as sf
import yaml

with open('character_config.yaml', 'r') as f:
    char_config = yaml.safe_load(f)

def get_wav_duration(path):
    with sf.SoundFile(path) as f:
        return len(f) / f.samplerate

print(' \n ========= Starting Chat... ================ \n')
if char_config["gpu_acceleration"] == "cuda":
    whisper_model = WhisperModel("base.en", device="cuda", compute_type="float16")
else: 
    whisper_model = WhisperModel("base.en", device="cpu", compute_type="float32")


while True:


    conversation_recording = output_wav_path = Path("audio") / "conversation.wav"
    conversation_recording.parent.mkdir(parents=True, exist_ok=True)

    record_on_speech(
            output_file=conversation_recording,
            samplerate=44100,
            channels=1,
            silence_threshold=0.02,  # Adjust based on your microphone sensitivity
            silence_duration=1,     # Stop after 3 seconds of silence
            device=None             # Use default device, or specify by ID or name
        )
    


    # Transcribe audio
    user_spoken_text = transcribe_audio(whisper_model, aud_path=conversation_recording)


    print("\n User : ", user_spoken_text)


    ### pass to LLM and get a LLM output.

    llm_output = llm_response(user_spoken_text)

    waifu_name = char_config["waifu_name"]
    print(f"{waifu_name} : \n", llm_output)

    # clean the LLM output for reading, you can configure this
    tts_read_text = clean_llm_output(llm_output)



    ### file organization for GPT-SoVITS

    # 1. Generate a unique filename
    uid = uuid.uuid4().hex
    filename = f"output_{uid}.wav"
    output_wav_path = Path("client","audio")/ filename
    public_audio_path = Path("audio")/ filename
    output_wav_path.parent.mkdir(parents=True, exist_ok=True)

    ### generate audio and save it to client/audio 
    gen_aud_path = sovits_gen(tts_read_text,output_wav_path)

    # Example
    duration = get_wav_duration(output_wav_path)

    vrm_talk(str(public_audio_path), "relaxed", llm_output, int(duration))



    print("waiting for audio to finish...")
    time.sleep(duration)


    # clean up audio files
    # [fp.unlink() for fp in Path("audio").glob("*.wav") if fp.is_file()]
