# from sheet_detector import MusicSheet
# from ultralytics import YOLO
import cv2
import logging
import os
import ActionScheduler


if __name__ == "__main__":
    # # Suppress YOLO logging, all but errors
    # logging.getLogger("ultralytics").setLevel(logging.ERROR)
    #
    # # Import the pretrained model for notes
    # model_note = YOLO(
    #    'C:/Users/Ilie/Desktop/facultate documente/licenta/SCRIPTS/MODELE/note detector (yolov8, 2 merged sets)/best.pt')

    # Get the images to process
    folder_path = 'C:/Users/Ilie/Desktop/facultate documente/licenta/SCRIPTS/sheet_detection/sheets/'
    allowed_extensions = ['.jpg', '.png', '.jpeg']
    images = [f for f in os.listdir(folder_path) if
              os.path.isfile(os.path.join(folder_path, f)) and os.path.splitext(f)[1].lower() in allowed_extensions]

    # --- PROCESS EACH IMAGE ---
    for img_idx, file in enumerate(images):
        # For testing; if you don't want to go through each image
        if img_idx >= 1:
            break

        # img = cv2.imread(folder_path + file)
        #
        # music_sheet = MusicSheet(img)
        #
        # music_sheet.set_folder_and_image_paths(folder_path, file)
        # music_sheet.set_model_note(model_note)
        #
        # music_sheet.resize_image(height=900)  # At the moment, there is some fine-tuning that is dependent on this scale
        #
        # music_sheet.run_detection()
        #
        # # music_sheet.show_results(show_noteheads_centroids=True, show_bounding_boxes=True, show_noteheads_contours=False)
        #
        # print([(key, list(group)) for key, group in music_sheet.time_series])

        time_series = [(0, [(0, -5, 0.25), (0, 'REST', 0.25)]),
         (0.25, [(0.25, -2.5, 0.25), (0.25, -10, 1), (0.25, -8, 1), (0.25, -12, 1)]), (0.5, [(0.5, -3, 0.25)]),
         (0.75, [(0.75, -3, 0.25)]), (1.0, [(1.0, -4, 0.125)]), (1.125, [(1.125, -5, 0.125)]),
         (1.25, [(1.25, -1, 0.5), (1.25, -8, 1), (1.25, -12, 1)]), (1.75, [(1.75, -1, 0.125), (1.75, 5, 0.125)]),
         (1.875, [(1.875, -2, 0.125)]), (2.0, [(2.0, 'REST', 0.25)]),
         (2.25, [(2.25, -2.5, 0.25), (2.25, -10, 1), (2.25, -12, 1)]), (2.5, [(2.5, -3, 0.25)]),
         (2.75, [(2.75, -3, 0.25)]), (3.0, [(3.0, -4, 0.125)]), (3.125, [(3.125, -5, 0.125)]),
         (3.25, [(3.25, -1, 0.5), (3.25, -8, 1), (3.25, -12, 1)]), (3.75, [(3.75, -1, 0.125)]),
         (3.875, [(3.875, -2, 0.125)]), (4.0, [(4.0, 'REST', 0.25)]), (4.25, [(4.25, -2.5, 0.25), (4.25, -12, 0.5)]),
         (4.5, [(4.5, -2, 0.125)]), (4.625, [(4.625, -1, 0.125)]), (4.75, [(4.75, -2, 0.25), (4.75, -9, 0.25)]),
         (5.0, [(5.0, -3, 0.25), (5.0, -9.5, 0.25)]), (5.25, [(5.25, -4, 0.5), (5.25, -11, 0.5)]),
         (5.75, [(5.75, 'REST', 0.25), (5.75, 'REST', 0.25)]), (6.0, [(6.0, -5, 0.25), (6.0, -12, 0.25)])]

        ActionScheduler.load_config()
        ActionScheduler.schedule_actions(time_series)
