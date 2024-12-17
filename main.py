from PIL import Image, ImageDraw, ImageFont # type: ignore
import pandas as pd # type: ignore
import requests
from io import BytesIO
import face_recognition
import numpy as np

class IDCardGenerator:
    def __init__(self, template_path):
        # Load the template
        self.template = Image.open(template_path)
        # A4 dimensions in pixels (at 300 DPI)
        self.a4_width = 2480  # 210mm
        self.a4_height = 3508  # 297mm
        
        # Calculate scaled template size to fit 2x3 grid with padding
        self.padding = 30  # padding between cards and edges
        available_width = (self.a4_width - (self.padding * 4)) / 3  # space for 3 columns
        available_height = (self.a4_height - (self.padding * 3)) / 2  # space for 2 rows
        
        # Calculate scale factor while maintaining aspect ratio
        width_scale = available_width / 630
        height_scale = available_height / 1080
        self.scale_factor = min(width_scale, height_scale)
        
        # New template dimensions
        self.template_width = int(630 * self.scale_factor)
        self.template_height = int(1080 * self.scale_factor)
        
    def create_id_cards_sheet(self, students_data):
        # Create blank A4 sheet
        a4_sheet = Image.new('RGB', (self.a4_width, self.a4_height), 'white')
        
        for idx, student in enumerate(students_data):
            if idx >= 6:  # Only 6 cards per sheet
                break
            
            # Calculate position in 2x3 grid
            row = idx // 3
            col = idx % 3
            
            # Calculate x and y positions with padding
            x = self.padding + col * (self.template_width + self.padding)
            y = self.padding + row * (self.template_height + self.padding)
            
            # Generate individual card
            card = self.create_id_card(
                name=student['Name'],
                zone=student['Zone'],
                photo_path=student['image'],
                output_path=None,  # Don't save individual cards
                scale_factor=self.scale_factor
            )
            
            # Paste card onto A4 sheet
            if card:
                a4_sheet.paste(card, (x, y))
        
        return a4_sheet
        
    def create_id_card(self, name, zone, photo_path, output_path=None, scale_factor=1,
                      photo_position=(315, 575),
                      photo_size=(435, 435),
                      name_position=(315, 850),
                      zone_position=(315, 940)):
        try:
            # Scale positions and sizes
            photo_position = tuple(int(p * scale_factor) for p in photo_position)
            photo_size = tuple(int(s * scale_factor) for s in photo_size)
            name_position = tuple(int(p * scale_factor) for p in name_position)
            zone_position = tuple(int(p * scale_factor) for p in zone_position)
            
            # Create a copy of the template and resize it
            card = self.template.copy()
            card = card.resize((self.template_width, self.template_height), Image.Resampling.LANCZOS)
            
            # Handle online image URL
            if photo_path.startswith(('http://', 'https://')):
                response = requests.get(photo_path)
                profile_photo = Image.open(BytesIO(response.content))
            else:
                profile_photo = Image.open(photo_path)
            
            # Convert PIL Image to numpy array for face detection
            photo_array = np.array(profile_photo)
            
            # Detect faces in the image
            face_locations = face_recognition.face_locations(photo_array)
            
            if face_locations:
                # Get the first face location (top, right, bottom, left)
                top, right, bottom, left = face_locations[0]
                
                # Calculate the center of the face
                face_center_x = (left + right) // 2
                face_center_y = (top + bottom) // 2
                
                # Calculate face height and add more padding (increased from 0.7 to 1.2)
                face_height = bottom - top
                padding = int(face_height * 1.2)  # 120% padding around the face
                
                # Calculate crop dimensions
                crop_size = max(right - left, bottom - top) + (padding * 2)
                
                # Ensure crop_size doesn't exceed image dimensions
                crop_size = min(crop_size, min(profile_photo.size))
                
                # Calculate crop coordinates
                left = max(0, face_center_x - crop_size // 2)
                top = max(0, face_center_y - crop_size // 2)
                right = min(profile_photo.width, left + crop_size)
                bottom = min(profile_photo.height, top + crop_size)
                
                # Crop the image around the face
                profile_photo = profile_photo.crop((left, top, right, bottom))
            else:
                # If no face detected, fall back to center crop
                width, height = profile_photo.size
                size = min(width, height)
                left = (width - size) // 2
                top = (height - size) // 2
                right = left + size
                bottom = top + size
                profile_photo = profile_photo.crop((left, top, right, bottom))

            # Resize and crop photo to fit circle without squeezing
            # Calculate dimensions to crop the image to a square
            width, height = profile_photo.size
            size = min(width, height)
            left = (width - size) // 2
            top = (height - size) // 2
            right = left + size
            bottom = top + size
            
            # Crop to square first
            profile_photo = profile_photo.crop((left, top, right, bottom))
            # Then resize to desired size
            profile_photo = profile_photo.resize(photo_size, Image.Resampling.LANCZOS)
            
            # Create circular mask
            mask = Image.new('L', photo_size, 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, photo_size[0], photo_size[1]), fill=255)
            
            # Apply circular mask
            output = Image.new('RGBA', photo_size, (0, 0, 0, 0))
            output.paste(profile_photo, (0, 0))
            output.putalpha(mask)
            
            # Calculate position to center the circular photo
            paste_x = photo_position[0] - photo_size[0]//2
            paste_y = photo_position[1] - photo_size[1]//2
            
            # Paste the circular photo
            card.paste(output, (paste_x, paste_y), output)
            
            # Add text
            draw = ImageDraw.Draw(card)
            
            # Adjust font sizes relative to template size
            name_font_size = int(self.template_height * 0.072)  # ~78px for 1080px height
            zone_font_size = int(self.template_height * 0.032)  # ~35px for 1080px height
            
            try:
                # Changed font to Berlin Sans FB Demi for name
                name_font = ImageFont.truetype("BRLNSDB.TTF", name_font_size)  # Berlin Sans FB Demi
                # Changed font to Degular Demo Medium for zone
                info_font = ImageFont.truetype("Degular-Medium.otf", zone_font_size)  # Degular Demo Medium
            except OSError as e:
                print(f"Font loading error: {str(e)}")
                print("Falling back to default fonts...")
                name_font = ImageFont.load_default()
                info_font = ImageFont.load_default()
            
            # Add name and zone with white color and center alignment
            name_bbox = draw.textbbox(name_position, name, font=name_font)
            name_x = name_position[0] - (name_bbox[2] - name_bbox[0])//2
            draw.text((name_x, name_position[1]), name, fill=(255, 255, 255), font=name_font)
            
            # Calculate zone text dimensions for background
            zone_bbox = draw.textbbox(zone_position, zone, font=info_font)
            zone_text_width = zone_bbox[2] - zone_bbox[0]
            zone_text_height = zone_bbox[3] - zone_bbox[1]
            
            # Calculate background rectangle dimensions with padding
            padding = 30
            rect_width = zone_text_width + (padding * 2)
            rect_height = zone_text_height + 20
            
            # Calculate rectangle position
            rect_x = zone_position[0] - rect_width // 2
            rect_y = zone_position[1] - (rect_height // 4) + (zone_text_height // 2)  # Adjusted for vertical centering
            
            # Draw rounded rectangle background
            corner_radius = 20  # You can adjust this value for different corner roundness
            draw.rounded_rectangle(
                [rect_x, rect_y, rect_x + rect_width, rect_y + rect_height],
                fill='#A75900',
                radius=corner_radius
            )
            
            # Draw zone text (moved after background)
            zone_x = zone_position[0] - (zone_bbox[2] - zone_bbox[0])//2
            draw.text((zone_x, zone_position[1]), zone, fill=(255, 255, 255), font=info_font)
            
            if output_path:
                card.save(output_path)
            return card
            
        except Exception as e:
            print(f"Error creating ID card: {str(e)}")
            return None

# Modified example usage
if __name__ == "__main__":
    generator = IDCardGenerator("template.png")
    
    try:
        df = pd.read_excel('stddetails.xlsx')
        
        # Calculate number of sheets needed
        num_sheets = (len(df) + 5) // 6  # Round up division by 6
        
        for sheet_num in range(num_sheets):
            # Get next 6 students
            start_idx = sheet_num * 6
            sheet_students = df[start_idx:start_idx + 6].to_dict('records')
            
            # Generate sheet with 6 cards
            sheet = generator.create_id_cards_sheet(sheet_students)
            
            # Save the sheet
            sheet.save(f"ID_Cards_Sheet_{sheet_num + 1}.png")
            
        print("ID card sheets generated successfully!")
    except Exception as e:
        print(f"Error generating ID card sheets: {str(e)}")
