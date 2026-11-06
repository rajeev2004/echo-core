"""Step 2: transport-only bot. Echoes mic audio back to prove the round trip."""

from loguru import logger
from pipecat.frames.frames import InputAudioRawFrame, OutputAudioRawFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.transports.base_transport import TransportParams

# One entry per transport; Twilio will be added later.
TRANSPORT_PARAMS = {
    "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
}


class EchoProcessor(FrameProcessor):
    """The output transport only plays OutputAudioRawFrame, so mic frames must be converted."""

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, InputAudioRawFrame):
            frame = OutputAudioRawFrame(frame.audio, frame.sample_rate, frame.num_channels)
        await self.push_frame(frame, direction)


async def bot(runner_args: RunnerArguments):
    transport = await create_transport(runner_args, TRANSPORT_PARAMS)

    pipeline = Pipeline([transport.input(), EchoProcessor(), transport.output()])
    task = PipelineTask(pipeline)

    @transport.event_handler("on_client_connected")
    async def on_connected(transport, client):
        logger.info("client connected")

    @transport.event_handler("on_client_disconnected")
    async def on_disconnected(transport, client):
        logger.info("client disconnected")
        await task.cancel()

    await PipelineRunner(handle_sigint=runner_args.handle_sigint).run(task)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
