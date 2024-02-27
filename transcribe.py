import os
import asyncio
import streamlit as st
import sounddevice
from amazon_transcribe.auth import AwsCrtCredentialResolver
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent
from dotenv import load_dotenv


load_dotenv()

AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')


latest_finalized_transcription = ""
transcription_started = False

class MyEventHandler(TranscriptResultStreamHandler):
    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        global latest_finalized_transcription
        # This handler can be implemented to handle transcriptions as needed.
        # Here's an example to get started.
        results = transcript_event.transcript.results
        for result in results:
            if result.is_partial == False:
                for alt in result.alternatives:
                    print(alt.transcript)
                    latest_finalized_transcription += alt.transcript

async def mic_stream(input_queue):
    loop = asyncio.get_event_loop()

    def callback(indata, frame_count, time_info, status):
        loop.call_soon_threadsafe(input_queue.put_nowait, (bytes(indata), status))

    # Be sure to use the correct parameters for the audio stream that matches
    # the audio formats described for the source language you'll be using:
    # https://docs.aws.amazon.com/transcribe/latest/dg/streaming.html
    stream = sounddevice.RawInputStream(
        channels=1,
        samplerate=16000,
        callback=callback,
        blocksize=1024 * 2,
        dtype="int16",
    )

    # Initiate the audio stream and asynchronously yield the audio chunks
    # as they become available.
    print(transcription_started)
    with stream:
        while transcription_started:
            indata, status = await input_queue.get()
            yield indata, status

async def write_chunks(stream, input_queue):
    # This connects the raw audio chunks generator coming from the microphone
    # and passes them along to the transcription stream.
    async for chunk, status in mic_stream(input_queue):
        await stream.input_stream.send_audio_event(audio_chunk=chunk)

async def basic_transcribe(input_queue):
    global transcription_started
    # Setup our client with the chosen AWS region
    client = TranscribeStreamingClient(region="us-east-1")
    # Start transcription to generate the async stream
    stream = await client.start_stream_transcription(
        language_code="en-US",
        media_sample_rate_hz=16000,
        media_encoding="pcm",
    )

    # Instantiate our handler and start processing events
    handler = MyEventHandler(stream.output_stream)

    try:
        if transcription_started:
            print(transcription_started)
            await asyncio.gather(write_chunks(stream, input_queue), handler.handle_events())
    except Exception as e:
        print("Error:", e)
    finally:
        transcription_started = False

def main():
    global transcription_started
    st.title("Real-Time Transcription")
    start_button = st.button("Start Transcription")
    stop_button = st.button("Stop Transcription")

    if start_button and not transcription_started:
        transcription_started = True


    if stop_button:
        transcription_started = False
        print(transcription_started)

    if transcription_started:
            st.write("Listening...")
            loop = asyncio.new_event_loop()  # Create a new event loop
            asyncio.set_event_loop(loop)  # Set it as the current event loop

            # Use a queue to communicate between mic_stream and basic_transcribe
            input_queue = asyncio.Queue()
            loop.run_until_complete(basic_transcribe(input_queue))
            loop.close()
            st.write(latest_finalized_transcription)

    st.write("Latest Finalized Transcription:")
    st.write(latest_finalized_transcription)

if __name__ == "__main__":
    main()
