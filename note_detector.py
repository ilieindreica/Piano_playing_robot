from collections import Counter
import cv2
import matplotlib.pyplot as plt
import os
from ultralytics import YOLO
import numpy as np


class Staff:
    def __init__(self):
        self.x1 = 0
        self.y1 = 0
        self.x2 = 0
        self.y2 = 0
        self.clef = ''
        self.window_pad = 0  # Padding around the staff to account for notes above or below when cropping the image

    def get_window(self):
        y1 = max(self.y1 - self.window_pad, 0)
        y2 = self.y2 + self.window_pad
        return y1, y2


if __name__ == "__main__":
    # Import the pretrained model
    model_path = "path/to/best.pt"
    model = YOLO(model_path)

    # Get the path to the images on which to work
    folder_path = 'path/to/sheets/'
    allowed_extensions = ['.jpg', '.png', '.jpeg']
    files = [f for f in os.listdir(folder_path) if
             os.path.isfile(os.path.join(folder_path, f)) and os.path.splitext(f)[1].lower() in allowed_extensions]

    for i, file in enumerate(files):
        # For testing; if you don't want to go through each image
        if i >= 20:
            break

        img = cv2.imread(folder_path + file)
        original_img = img
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Resize image, keeping aspect-ratio
        height, width = img.shape
        ratio = height / width
        new_height = 900
        new_width = int(new_height / ratio)
        img = cv2.resize(img, (new_width, new_height))
        original_img = cv2.resize(original_img, (new_width, new_height))

        # ---------- Use the model to make predictions -------------
        results = model(folder_path + file)
        results = results[0]
        # Get the midpoints and heights of detected boxes in corresponding lists
        treble_clefs = []
        bass_clefs = []
        class_names = results.names
        for box in results.boxes:
            cls = box.cls.item()
            point = box.xyxyn[0]  # [0] because tensors
            x1 = round(point[0].item() * new_width)
            y1 = round(point[1].item() * new_height)
            x2 = round(point[2].item() * new_width)
            y2 = round(point[3].item() * new_height)
            if class_names[cls] == 'Treble-clef':
                treble_clefs.append((x1, y1, x2, y2))
            elif class_names[cls] == 'Bass-clef':
                bass_clefs.append((x1, y1, x2, y2))

        # Convert to binary image, and make the objects white (in music sheets they appear as black)
        # This is so that when doing the sum over the columns for histogram,
        # the higher values will be for objects of interest
        _, img = cv2.threshold(img, 210, 255, cv2.THRESH_BINARY)
        img = (255 - img) // 255
        img2 = img * 255

        # =================== Detect staffs ========================
        # Create row histogram
        h_series = list(range(new_height))
        row_histogram = []
        for row in img:
            s = 0
            for elem in row:
                s += elem
            row_histogram.append(s)

        max_row_hist = max(row_histogram)
        search_col_index = round(4 / 5 * max_row_hist)

        # DEFINITION: black_rows= the rows with the highest values in the row histogram (as a fraction of the max value)
        # The indices of the black_rows (the heights at which they appear in the image)
        indices = [i for i, v in enumerate(row_histogram) if v >= 4 / 5 * max_row_hist]
        line_width = 1
        space_width = []
        all_line_widths = []
        line_beginnings = [indices[0]]
        # Adjacent black_rows are part of the same line; from this we can determine the average line width
        for j in range(1, len(indices)):
            dif = indices[j] - indices[j - 1]
            if dif == 1:          # Check if lines are within ±1; this means they are part of the same staff line
                line_width += 1
            else:                 # If not, it means we hit a space between lines, and 'dif' indicates its width
                all_line_widths.append(line_width)
                line_width = 1
                space_width.append(dif - 1)         # -1 to not count one of the black_rows as white space
                line_beginnings.append(indices[j])  # A new line begins

        all_line_widths.append(line_width)
        staffline_width = Counter(all_line_widths).most_common(1)[0][0]
        staffline_space_width = Counter(space_width).most_common(1)[0][0]

        # Determine staffs as consecutive lines close to each other
        tolerance = 4
        space_between_line_beginnings = staffline_space_width + staffline_width + tolerance
        num_of_staff_lines = 5
        consecutives = 1
        beginning_of_staff = line_beginnings[0]
        all_staffs = []
        for j in range(1, len(line_beginnings)):
            staff = Staff()
            b = line_beginnings[j]
            if b - line_beginnings[j - 1] <= space_between_line_beginnings:
                consecutives += 1
            else:
                consecutives = 1
                beginning_of_staff = b
            if consecutives == num_of_staff_lines:
                staff.y1 = beginning_of_staff
                staff.y2 = b + staffline_width  # Add line_width to match the end of staff
                # Multiply by the max supposed number of notes above or below staff
                staff.window_pad = (space_between_line_beginnings - tolerance) * 4
                all_staffs.append(staff)
                beginning_of_staff = b
                consecutives = 1

        # Create column histogram
        w_series = list(range(new_width))
        col_histogram = []
        for col_idx in range(img.shape[1]):
            s = 0
            for elem in img[:, col_idx]:
                s += elem
            col_histogram.append(s)

        model_note = YOLO('path/to/best.pt')
        # Crop the image for staffs
        for idx, s in enumerate(all_staffs):
            y1, y2 = s.get_window()
            crop = np.copy(original_img[y1:y2, 0:new_width])
            # crop = original_img[y1:y2, 0:new_width]
            cv2.imwrite('temp.jpg', crop)
            r = model_note('temp.jpg')[0]

            for box in r.boxes.xyxy:  
                x1, y1, x2, y2 = map(int, box) 
                cv2.rectangle(crop, (x1, y1), (x2, y2), (0, 255, 0), 2)  

                # Display the image
            cv2.imshow(f'Crop {idx}', crop)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        # ========================== Plots ==========================
        # # Show the original image
        # for x1, y1, x2, y2 in treble_clefs:
        #     original_img = cv2.rectangle(original_img, (x1, y1), (new_width, y2), (120, 0, 0), 3)
        # for x1, y1, x2, y2 in bass_clefs:
        #     original_img = cv2.rectangle(original_img, (x1, y1), (new_width, y2), (120, 0, 0), 3)
        # for index in all_staffs:
        #     original_img = cv2.line(original_img, (0, index[0]), (new_width, index[0]), (255, 0, 0), 1)
        #     original_img = cv2.line(original_img, (0, index[1]), (new_width, index[1]), (255, 0, 0), 1)

        cv2.imshow('img', original_img)
        # cv2.imshow('img2', img2)

        # Plot the histograms in 2 subplots
        plt.figure(figsize=(9, 6))
        plt.subplot(1, 2, 1)
        plt.plot(row_histogram, h_series, color='black')
        plt.fill_between(row_histogram, h_series, color='black')
        plt.title('Row histogram')

        plt.axvline(search_col_index, color='r')
        plt.gca().invert_yaxis()

        plt.subplot(1, 2, 2)
        plt.plot(w_series, col_histogram, color='black')
        plt.gca().invert_yaxis()
        plt.fill_between(w_series, col_histogram, color='black')
        plt.title('Column histogram')

        plt.get_current_fig_manager().window.wm_geometry("+700+150")  # Position the plot on screen
        plt.show()



