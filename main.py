from PIL import Image, ImageDraw, ImageFont # type: ignore
import pandas as pd # type: ignore
import requests
from io import BytesIO

class IDCardGenerator:
    def __init__(self, template_path):
        # Load the template
        self.template = Image.open(template_path)
        # Template dimensions
        self.template_width = 630
        self.template_height = 1080
        
    def create_id_card(self, name, zone, photo_path, output_path,
                      photo_position=(315, 575),    # Horizontally centered (630/2), ~450px from top
                      photo_size=(435, 435),        # Circular photo size
                      name_position=(315, 850),     # Centered horizontally, ~880px from top
                      zone_position=(315, 940)):    # Centered horizontally, ~950px from top
        try:
            # Create a copy of the template
            card = self.template.copy()
            
            # Handle online image URL
            if photo_path.startswith(('http://', 'https://')):
                response = requests.get(photo_path)
                profile_photo = Image.open(BytesIO(response.content))
            else:
                profile_photo = Image.open(photo_path)
            
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
            
            card.save(output_path)
            return True
            
        except Exception as e:
            print(f"Error creating ID card: {str(e)}")
            return False

# Modified example usage
if __name__ == "__main__":
    # Initialize with your template
    generator = IDCardGenerator("template.png")  # Replace with your template path
    
    # Read student data from Excel
    try:
        df = pd.read_excel('stddetails.xlsx')
        
        # Generate ID cards for each student in the Excel file
        for index, student in df.iterrows():
            generator.create_id_card(
                name=student['Name'],
                zone=student['Zone'],
                photo_path=student['image'],
                output_path=f"ID_Card_{student['Name'].replace(' ', '_')}.png"
            )
        print("ID cards generated successfully!")
    except Exception as e:
        print(f"Error reading Excel file or generating cards: {str(e)}")
