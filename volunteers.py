from PIL import Image, ImageDraw, ImageFont # type: ignore
import pandas as pd # type: ignore
import requests
from io import BytesIO
import face_recognition
import numpy as np
import os
from PIL.Image import Image as PILImage
from tqdm import tqdm  # Add this import at the top

class IDCardGenerator:
    def __init__(self, template_path):
        # Load the template
        self.template = Image.open(template_path)
        # New paper dimensions
        self.a4_width = 3900
        self.a4_height = 5700
        
        # New ID card dimensions
        self.card_base_width = 768
        self.card_base_height = 1299
        
        # Calculate padding for 4x5 grid
        self.horizontal_padding = (self.a4_width - (self.card_base_width * 5)) // 6
        self.vertical_padding = (self.a4_height - (self.card_base_height * 4)) // 5
        
        # Use exact dimensions without scaling
        self.template_width = self.card_base_width
        self.template_height = self.card_base_height
        self.scale_factor = 1.0
        
    def create_id_cards_sheet(self, students_data):
        # Create blank sheet
        a4_sheet = Image.new('RGB', (self.a4_width, self.a4_height), 'white')
        
        for idx, student in enumerate(students_data):
            if idx >= 20:  # Now 20 cards per sheet (4x5 grid)
                break
            
            # Calculate position in 4x5 grid
            row = idx // 5  # 5 columns
            col = idx % 5
            
            # Calculate x and y positions with padding
            x = self.horizontal_padding + col * (self.template_width + self.horizontal_padding)
            y = self.vertical_padding + row * (self.template_height + self.vertical_padding)
            
            # Generate individual card
            card = self.create_id_card(
                name=student['Name'],
                zone=student['Zone'],
                ministry=student['Ministry'],
                photo_path=student['image'],
                output_path=None,
                scale_factor=1.0
            )
            
            # Paste card onto sheet
            if card:
                a4_sheet.paste(card, (x, y))
        
        return a4_sheet
        
    def create_id_card(self, name, zone, ministry, photo_path, output_path=None, scale_factor=1,
                      photo_position=(384, 700),  # Adjusted for new dimensions
                      photo_size=(512, 512),
                      name_position=(390, 990),
                      zone_position=(390, 1095),
                      ministry_position=(390, 1160)):
        try:
            # Convert any non-string inputs to strings
            name = str(name)
            zone = str(zone)
            ministry = str(ministry)
            
            # Create a copy of the template and resize it to exact dimensions
            card = self.template.copy()
            card = card.resize((self.template_width, self.template_height), Image.Resampling.LANCZOS)
            
            # Handle online image URL
            if photo_path.startswith(('http://', 'https://')):
                response = requests.get(photo_path)
                profile_photo = Image.open(BytesIO(response.content))
            else:
                profile_photo = Image.open(photo_path)
            
            # Convert image to RGB mode
            profile_photo = profile_photo.convert('RGB')
            
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
                padding = int(face_height * 1.5)  # 120% padding around the face
                
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
            # Base font size based on template size or a predefined size
            base_name_font_size = int(self.template_height * 0.072)  # ~78px for 1080px height

            # Adjust name font size based on length
            if len(name) <= 13:
                name_font_size = base_name_font_size  # 100% of base size
            elif 14 <= len(name) <= 15:
                # ~85% of base size
                name_font_size = int(base_name_font_size * 0.85)
            elif 16 <= len(name) <= 19:
                # ~70% of base size
                name_font_size = int(base_name_font_size * 0.80)
            else:
                # If name exceeds 17 characters, reduce further, for example to 60% (can be adjusted)
                name_font_size = int(base_name_font_size * 0.65)

            
            zone_font_size = int(self.template_height * 0.032)  # ~35px for 1080px height
            
            try:
                # Changed font to Berlin Sans FB Demi for name
                name_font = ImageFont.truetype("DegularDisplay-Bold.otf", name_font_size)  # Now using adjusted size
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
            
            # Replace zone text with "Volunteer"
            volunteer_text = "Volunteer"
            
            # Calculate volunteer text dimensions for background
            volunteer_bbox = draw.textbbox(zone_position, volunteer_text, font=info_font)
            volunteer_text_width = volunteer_bbox[2] - volunteer_bbox[0]
            volunteer_text_height = volunteer_bbox[3] - volunteer_bbox[1]
            
            # Calculate background rectangle dimensions with padding
            padding = 30
            rect_width = volunteer_text_width + (padding * 2)
            rect_height = volunteer_text_height + 20
            
            # Calculate rectangle position
            rect_x = zone_position[0] - rect_width // 2
            rect_y = zone_position[1] - (rect_height // 4) + (volunteer_text_height // 2)
            
            # Draw rounded rectangle background
            corner_radius = 15
            draw.rounded_rectangle(
                [rect_x, rect_y, rect_x + rect_width, rect_y + rect_height],
                fill='#693800',
                radius=corner_radius
            )
            
            # Draw volunteer text
            volunteer_x = zone_position[0] - (volunteer_bbox[2] - volunteer_bbox[0])//2
            draw.text((volunteer_x, zone_position[1]), volunteer_text, fill=(255, 255, 255), font=info_font)
            
            # Add ministry text without background
            # Calculate maximum width for text with 50px padding on each side
            max_text_width = self.template_width - 100  # 50px padding on each side
            
            # Function to wrap text
            def wrap_text(text, font, max_width):
                # Convert any non-string input to string
                text = str(text)
                words = text.split()
                lines = []
                current_line = []
                
                for word in words:
                    current_line.append(word)
                    # Check if current line width exceeds max_width
                    test_line = ' '.join(current_line)
                    bbox = draw.textbbox((0, 0), test_line, font=info_font)
                    if bbox[2] - bbox[0] > max_width:
                        # Remove last word and add current line to lines
                        if len(current_line) > 1:
                            current_line.pop()
                            lines.append(' '.join(current_line))
                            current_line = [word]
                        else:
                            # If single word is too long, just add it
                            lines.append(test_line)
                            current_line = []
                
                if current_line:
                    lines.append(' '.join(current_line))
                return lines

            # Wrap ministry text
            ministry_lines = wrap_text(ministry, info_font, max_text_width)
            line_height = zone_font_size * 1.2  # 120% of font size for line spacing
            
            # Calculate total height needed for all ministry lines
            total_ministry_height = len(ministry_lines) * line_height
            
            # Calculate background rectangle dimensions for ministry text
            ministry_padding = 30
            max_ministry_width = 0
            
            # Find the widest line of text
            for line in ministry_lines:
                ministry_bbox = draw.textbbox((0, 0), line, font=info_font)
                line_width = ministry_bbox[2] - ministry_bbox[0]
                max_ministry_width = max(max_ministry_width, line_width)
            
            ministry_rect_width = max_ministry_width + (ministry_padding * 2)
            ministry_rect_height = total_ministry_height + 3
            
            # Calculate rectangle position for ministry
            ministry_rect_x = ministry_position[0] - ministry_rect_width // 2
            ministry_rect_y = ministry_position[1] - (ministry_rect_height // 4) + (zone_font_size // 2)
            
            # Draw rounded rectangle background for ministry
            draw.rounded_rectangle(
                [ministry_rect_x, ministry_rect_y, 
                 ministry_rect_x + ministry_rect_width, 
                 ministry_rect_y + ministry_rect_height],
                fill='#ffffff',
                radius=15
            )
            
            # Draw each line of ministry text
            for i, line in enumerate(ministry_lines):
                ministry_bbox = draw.textbbox(ministry_position, line, font=info_font)
                ministry_x = ministry_position[0] - (ministry_bbox[2] - ministry_bbox[0])//2
                y_position = ministry_position[1] + (i * line_height)
                draw.text((ministry_x, y_position), line, fill=(227, 73, 0), font=info_font)

            if output_path:
                card.save(output_path)
            return card
            
        except Exception as e:
            print(f"Error creating ID card: {str(e)}")
            return None

    def save_image_as_pdf(self, image: PILImage, output_path: str) -> None:
        """Convert PIL Image to PDF and save it"""
        # Convert the image to RGB mode if it isn't already
        if image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(output_path, 'PDF', resolution=300.0)

# Modified example usage
if __name__ == "__main__":
    generator = IDCardGenerator("template2.png")
    
    try:
        os.makedirs('volunteers', exist_ok=True)
        
        df = pd.read_excel('volunteers.xlsx')
        
        # Calculate number of sheets needed (20 cards per sheet now)
        num_sheets = (len(df) + 19) // 20  # Round up division by 20
        
        print(f"Generating {num_sheets} sheets of ID cards...")
        
        # Add progress bar
        for sheet_num in tqdm(range(num_sheets), desc="Generating ID Cards", unit="sheet"):
            # Get next 20 students
            start_idx = sheet_num * 20
            sheet_students = df[start_idx:start_idx + 20].to_dict('records')
            
            # Generate sheet with 20 cards
            sheet = generator.create_id_cards_sheet(sheet_students)
            
            # Save the sheet as PDF instead of PNG
            output_path = f"volunteers/ID_Cards_Sheet_{sheet_num + 1}.pdf"
            generator.save_image_as_pdf(sheet, output_path)
        
        print("\nID card sheets generated successfully!")
    except Exception as e:
        print(f"Error generating ID card sheets: {str(e)}")
