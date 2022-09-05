#!/usr/bin/env python3

# Copyright (c) 2020-2022, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

import os, sys, shutil
import argparse
from tqdm import tqdm

import common
import pyngp as ngp # noqa
import numpy as np
import cv2

import time
from threading import Thread
from queue import Queue


class AsyncFrameSetRecorder:
    def __init__(self, output_path: str = "recordings"):
        self.output_path = output_path
        self._frames = Queue()

        self._running = True

        self._writer_thread = Thread(target=self._writer_loop, daemon=True)
        self._writer_thread.start()

        self._image_index = 0

    def open(self):
        self._image_index = 0
        os.makedirs(self.output_path, exist_ok=True)

    def add_image(self, image: np.ndarray):
        self._frames.put(image)

    def close(self):
        while not self._frames.empty():
            time.sleep(0.1)

    def shutdown(self):
        self.close()
        self._running = False

    def _writer_loop(self):
        while self._running or not self._frames.empty():
            image = self._frames.get()
            self._write_image(self._image_index, image)
            self._image_index += 1

    def _write_image(self, id: int, image: np.ndarray):
        output_path = os.path.join(self.output_path, f"{id:04d}.png")
        cv2.imwrite(output_path, image)


def render_video(resolution, numframes, scene, name, spp, fps, exposure=0):
	testbed = ngp.Testbed(ngp.TestbedMode.Nerf)
	# testbed.load_snapshot("data/toy/base.msgpack")
	# testbed.load_camera_path("data/toy/base_cam.json")
	testbed.load_snapshot(os.path.join(scene, "base.msgpack"))
	testbed.load_camera_path(os.path.join(scene, "base_cam.json"))

	if 'temp' in os.listdir():
		shutil.rmtree('temp')
	os.makedirs('temp')

	recorder = AsyncFrameSetRecorder("temp/")
	recorder.open()

	for i in tqdm(list(range(min(numframes,numframes+1))), unit="frames", desc=f"Rendering"):
		testbed.camera_smoothing = i > 0
		frame = testbed.render(resolution[0], resolution[1], spp, True, float(i)/numframes, float(i + 1)/numframes, fps, shutter_fraction=0.5)

		if i == 0:
			continue

		ix = i - 1

		# common.write_image(f"temp/{ix:04d}.png", np.clip(frame * 2**exposure, 0.0, 1.0), quality=100)
		img = convert_to_img(frame, exposure)
		recorder.add_image(img)
		# cv2.imwrite(f"temp/{ix:04d}.png", img)

	print("waiting for recorder to write all files...")
	recorder.shutdown()

	output_name = os.path.join(scene, f"{name}.mp4")
	os.system(f"ffmpeg -i temp/%04d.png -vf \"fps={fps}\" -c:v libx264 -crf 20 -pix_fmt yuv420p {output_name}")
	# shutil.rmtree('temp')

def convert_to_img(frame, exposure):
	img = np.clip(frame * 2**exposure, 0.0, 1.0)

	# Unmultiply alpha
	img[...,0:3] = np.divide(img[...,0:3], img[...,3:4], out=np.zeros_like(img[...,0:3]), where=img[...,3:4] != 0)
	img[...,0:3] = common.linear_to_srgb(img[...,0:3])

	img = (np.clip(img, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
	img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
	return img

def parse_args():
	parser = argparse.ArgumentParser(description="render neural graphics primitives testbed, see documentation for how to")
	parser.add_argument("--scene", "--training_data", default="", help="The scene to load. Can be the scene's name or a full path to the training data.")

	parser.add_argument("--width", "--screenshot_w", type=int, default=1920, help="Resolution width of the render video")
	parser.add_argument("--height", "--screenshot_h", type=int, default=1080, help="Resolution height of the render video")
	parser.add_argument("--n_seconds", type=int, default=1, help="Number of steps to train for before quitting.")
	parser.add_argument("--fps", type=int, default=60, help="number of fps")
	parser.add_argument("--render_name", type=str, default="", help="name of the result video")


	args = parser.parse_args()
	return args

if __name__ == "__main__":
	args = parse_args()

	render_video([args.width, args.height], args.n_seconds*args.fps, args.scene, args.render_name, spp=8, fps=args.fps)
