import argparse
from glob import glob
import os
import warnings

import cv2
import numpy as np
from tqdm import tqdm

from face_detector_threaded import FaceDetector

"""
Given a folder of images or videos, run a face detector (literally a FaceDetector) on all images 
or videos in the folder. Detects and crop all faces in the images or every 1/rate frames from the videos. 
Save the resulting crops as .jpgs in an output folder. 
"""

warnings.filterwarnings('once')
IMAGE_EXT = ['.jpg', '.JPG', '.png', '.PNG']
VIDEO_EXT = ['.mp4', '.MP4', 'mov', '.MOV']


def get_images(input_dir):
    """
    Get filenames of images from the input directory.
    @param input_dir: Directory containing images to extract faces from.
    @return: List of image filenames.
    """
    files = [glob(f"{input_dir}/*{e}") for e in IMAGE_EXT]
    return files[0]


def get_videos(input_dir):
    """
    Get filenames of videos from the input directory.
    @param input_dir: Directory containing videos to extract faces from.
    @return: List of video filenames.
    """
    files = [glob(f"{input_dir}/*{e}") for e in VIDEO_EXT]
    return files[0]


def crop_and_save_img(frame, file_num, output_dir):
    """Run frame through FaceDetector and save the cropped face image."""
    if frame is not None and not 0:
        boxes = face_detector.detect(frame)
        for box in boxes:
            # Get individual coordinates as integers
            x1, y1, x2, y2 = [int(b) for b in box]
            face = frame[y1:y2, x1:x2]
            if face is None or 0 in face.shape:
                continue
            face_file_name = os.path.join(output_dir, f'{file_num}.jpg')
            cv2.imwrite(face_file_name, face)


def crop_faces_from_images(output_dir):
    """Iterate through images and crop and save faces."""
    file_num = 0
    for i in filenames:
        image = cv2.imread(i)
        crop_and_save_img(np.float32(image), file_num, output_dir)
        file_num += 1


def crop_faces_from_videos(output_dir):
    """Iterate through video frames and crop and save faces."""
    file_num = 0
    for video_file in filenames:
        print(f"Opening {video_file}")
        video = cv2.VideoCapture(video_file)
        file_len = int(video.get(cv2.CAP_PROP_FRAME_COUNT))

        for frame_num in tqdm(range(file_len)):
            ret, frame = video.read()

            if frame_num % args.rate == 0:
                # If the video is shot horizontally, flip it so it's in the right orientation
                if args.horiz:
                    frame = cv2.transpose(frame)
                crop_and_save_img(frame, file_num, output_dir)
                file_num += 1

        video.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Crop faces from a set of images or videos using a face detector. Save the cropped faces as images.")
    parser.add_argument("--input_dir", default="videos", type=str, help="Input directory containing the videos/images.")
    parser.add_argument('--output_dir', default='face_imgs', type=str, help="Output directory for the extracted faces.")
    parser.add_argument('--trained_model', default='blazeface.pth', type=str, help="Path to the face detector model.")
    parser.add_argument('--images', default=False, action='store_true',
                        help='Crop faces from images instead of videos.')
    parser.add_argument('--rate', default=5, type=int, help="Crop faces from every 1/rate frames of the video.")
    parser.add_argument('--horiz', default=False, action='store_true', help='Rotate the video. If your output images '
                                                                            'are all sideways, enable this.')
    args = parser.parse_args()

    face_detector = FaceDetector(trained_model=args.trained_model)
    filenames = get_images(args.input_dir) if args.images else get_videos(args.input_dir)

    if not os.path.isdir(args.output_dir):
        os.mkdir(args.output_dir)

    if args.images:
        crop_faces_from_images(args.output_dir)
    else:
        crop_faces_from_videos(args.output_dir)

    exit(0)
