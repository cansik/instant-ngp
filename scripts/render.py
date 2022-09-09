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

def set_crop_size(testbed, crop_size):
	cen = testbed.render_aabb.center()
	diag = np.array([crop_size, crop_size, crop_size])
	bbox = ngp.BoundingBox(cen - diag * 0.5, cen + diag * 0.5)

	testbed.render_aabb.min = bbox.min
	testbed.render_aabb.max = bbox.max

def render_video(resolution, numframes, scene, name, spp, fps, camera_smoothing, exposure=0, crop_size = None):
	testbed = ngp.Testbed(ngp.TestbedMode.Nerf)
	testbed.load_snapshot(os.path.join(scene, "base.msgpack"))
	testbed.load_camera_path(os.path.join(scene, "base_cam.json"))

	testbed.camera_smoothing = camera_smoothing

	if crop_size is not None:
		set_crop_size(testbed, crop_size)

	if 'temp' in os.listdir():
		shutil.rmtree('temp')
	os.makedirs('temp')

	recorder = AsyncFrameSetRecorder("temp/")
	recorder.open()

	for i in tqdm(list(range(min(numframes,numframes+1))), unit="frames", desc=f"Rendering"):
		frame = testbed.render(resolution[0], resolution[1], spp, True, float(i)/numframes, float(i + 1)/numframes, fps, shutter_fraction=0.5)

		if i == 0:
			continue

		img = convert_to_img(frame, exposure)
		recorder.add_image(img)

	print("waiting for recorder to write all files...")
	recorder.shutdown()

	output_name = os.path.join(scene, f"{name}.mp4")
	os.system(f"ffmpeg -i temp/%04d.png -vf \"fps={fps}\" -c:v libx264 -crf 20 -pix_fmt yuv420p -y {output_name}")

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
	parser.add_argument("--spp", type=int, default=8, help="number of fps")
	parser.add_argument("--crop-size", type=float, default=None, help="crop size")
	parser.add_argument("--camera-smoothing", action="store_true", help="smooth camera")
	parser.add_argument("--render_name", type=str, default="", help="name of the result video")


	args = parser.parse_args()
	return args

if __name__ == "__main__":
	args = parse_args()

	render_video([args.width, args.height], args.n_seconds*args.fps, args.scene, args.render_name,
				 spp=args.spp, fps=args.fps, camera_smoothing=args.camera_smoothing, crop_size=args.crop_size)
