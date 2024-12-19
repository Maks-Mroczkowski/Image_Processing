import math
import zlib

class PNG:
    def __init__(self):
        self.data = b''
        self.info = ''
        self.width = 0
        self.height = 0
        self.bit_depth = 0
        self.color_type = 0
        self.compress = 0
        self.filter = 0
        self.interlace = 0
        self.img = []

    def load_file(self, file_name):
        try:
            with open(file_name, 'rb') as file:
                self.data = file.read()
            self.info = file_name
        except FileNotFoundError:
            self.info = 'file not found'

    def valid_png(self):
        # PNG signature: 8 bytes
        # This is the standard 8-byte PNG signature used for validation.
        signature = b'\x89PNG\r\n\x1a\n'
        return self.data[:8] == signature

    def validate_crc(self, chunk_type, chunk_data, expected_crc):
        """
        Validate the CRC for a given PNG chunk.
        :param chunk_type: The type of the chunk (4-character string).
        :param chunk_data: The data of the chunk (bytes).
        :param expected_crc: The CRC value from the PNG file (integer).
        :raises ValueError: If the CRC validation fails.
        """
        actual_crc = zlib.crc32(chunk_type.encode() + chunk_data) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise ValueError(f"CRC mismatch for chunk {chunk_type}. Expected {expected_crc}, got {actual_crc}.")

    def read_header(self):
        # IHDR is the first chunk after the signature, starts at byte 8
        header_start = 8
        ihdr_chunk_length = 13  # IHDR data length (does not include type or CRC)
        chunk_type = self.data[header_start + 4 : header_start + 8].decode()
        chunk_data = self.data[header_start + 8 : header_start + 8 + ihdr_chunk_length]
        chunk_crc = int.from_bytes(self.data[header_start + 8 + ihdr_chunk_length : header_start + 12 + ihdr_chunk_length], 'big')

        # Validate CRC to ensure the integrity of the IHDR chunk
        self.validate_crc(chunk_type, chunk_data, chunk_crc)

        # Parse IHDR and update attributes
        self.width = int.from_bytes(chunk_data[0:4], 'big')
        self.height = int.from_bytes(chunk_data[4:8], 'big')
        self.bit_depth = chunk_data[8]
        self.color_type = chunk_data[9]
        self.compress = chunk_data[10]
        self.filter = chunk_data[11]
        self.interlace = chunk_data[12]

        # Validate IHDR specifications to ensure they meet the expected criteria
        if (
            self.bit_depth != 8
            or self.color_type != 2
            or self.compress != 0
            or self.filter != 0
            or self.interlace != 0
        ):
            raise ValueError("Unsupported IHDR specifications.")

    def read_chunks(self):
        self.img = []
        data_start = 33  # After IHDR
        i = 0
        idat_data = b""  # Accumulate all IDAT data here

        while i < len(self.data) - 12:  # Ensure we don't go past the end
            chunk_length = int.from_bytes(self.data[data_start + i : data_start + i + 4], 'big')
            chunk_type = self.data[data_start + i + 4 : data_start + i + 8].decode()
            chunk_data = self.data[data_start + i + 8 : data_start + i + 8 + chunk_length]
            chunk_crc = int.from_bytes(self.data[data_start + i + 8 + chunk_length : data_start + i + 12 + chunk_length], 'big')

            try:
                # Validate CRC to ensure the integrity of each chunk
                self.validate_crc(chunk_type, chunk_data, chunk_crc)
            except ValueError as e:
                print(f"Warning: {e}. Skipping chunk {chunk_type}.")
                i += 8 + chunk_length + 4
                continue

            if chunk_type == "IDAT":
                # This line accumulates all IDAT chunk data for later decompression
                idat_data += chunk_data  # Concatenate all IDAT chunks
            elif chunk_type == "IEND":
                break
            # Ignore all other chunks
            i += 8 + chunk_length + 4  # Move to the next chunk

        try:
            # Decompress accumulated IDAT data to retrieve pixel information
            decompressed_data = zlib.decompress(idat_data)
        except zlib.error as e:
            raise ValueError(f"Failed to decompress IDAT data: {e}")

        # Parse the decompressed data
        row_size = self.width * 3  # RGB pixels
        row_offset = 0
        for j in range(self.height):
            if row_offset >= len(decompressed_data):
                raise ValueError("Decompressed data is shorter than expected.")

            filter_type = decompressed_data[row_offset]
            if filter_type > 4:
                print(f"Warning: Unsupported filter type {filter_type} at row {j}. Skipping this row.")
                row_offset += 1 + row_size
                continue

            row_data = decompressed_data[row_offset + 1 : row_offset + 1 + row_size]

            # Parse RGB pixel data from a row into a structured format
            if filter_type == 0:  # No filter
                parsed_row = [[row_data[k], row_data[k + 1], row_data[k + 2]] for k in range(0, len(row_data), 3)]
            elif filter_type == 1:  # Sub filter
                parsed_row = []
                for k in range(0, len(row_data), 3):
                    prev_pixel = parsed_row[-1] if k > 0 else [0, 0, 0]
                    r = (row_data[k] + prev_pixel[0]) % 256
                    g = (row_data[k + 1] + prev_pixel[1]) % 256
                    b = (row_data[k + 2] + prev_pixel[2]) % 256
                    parsed_row.append([r, g, b])
            elif filter_type == 2:  # Up filter
                prev_row = self.img[j - 1] if j > 0 else [[0, 0, 0]] * (self.width)
                parsed_row = []
                for k in range(0, len(row_data), 3):
                    r = (row_data[k] + prev_row[k // 3][0]) % 256
                    g = (row_data[k + 1] + prev_row[k // 3][1]) % 256
                    b = (row_data[k + 2] + prev_row[k // 3][2]) % 256
                    parsed_row.append([r, g, b])
            elif filter_type == 3:  # Average filter
                parsed_row = []
                prev_row = self.img[j - 1] if j > 0 else [[0, 0, 0]] * (self.width)
                for k in range(0, len(row_data), 3):
                    left = parsed_row[-1] if k > 0 else [0, 0, 0]
                    above = prev_row[k // 3] if j > 0 else [0, 0, 0]

                    r = (row_data[k] + ((left[0] + above[0]) // 2)) % 256
                    g = (row_data[k + 1] + ((left[1] + above[1]) // 2)) % 256
                    b = (row_data[k + 2] + ((left[2] + above[2]) // 2)) % 256
                    parsed_row.append([r, g, b])
            elif filter_type == 4:  # Paeth filter
                parsed_row = []
                prev_row = self.img[j - 1] if j > 0 else [[0, 0, 0]] * (self.width)
                for k in range(0, len(row_data), 3):
                    a = parsed_row[-1] if k > 0 else [0, 0, 0]  # Left
                    b = prev_row[k // 3] if j > 0 else [0, 0, 0]  # Above
                    c = prev_row[k // 3 - 1] if (j > 0 and k > 0) else [0, 0, 0]  # Top-left

                    def paeth_predictor(left, above, upper_left):
                        p = left + above - upper_left
                        pa = abs(p - left)
                        pb = abs(p - above)
                        pc = abs(p - upper_left)
                        if pa <= pb and pa <= pc:
                            return left
                        elif pb <= pc:
                            return above
                        else:
                            return upper_left

                    r = (row_data[k] + paeth_predictor(a[0], b[0], c[0])) % 256
                    g = (row_data[k + 1] + paeth_predictor(a[1], b[1], c[1])) % 256
                    b = (row_data[k + 2] + paeth_predictor(a[2], b[2], c[2])) % 256
                    parsed_row.append([r, g, b])
            else:
                raise ValueError(f"Unsupported filter type: {filter_type}")

            self.img.append(parsed_row)
            row_offset += 1 + row_size  # Move to new row

    def save_rgb(self, file_name, rgb_option):
        if not (1 <= rgb_option <= 3):
            raise ValueError("rgb_option must be 1 (red), 2 (green), or 3 (blue).")
        channel = rgb_option - 1

        image_data = b""
        for row in self.img:
            image_data += b"\x00"  # No filter
            for pixel in row:
                # Set only the selected channel, others to 0
                new_pixel = [0, 0, 0]
                new_pixel[channel] = pixel[channel]
                image_data += bytes(new_pixel)

        # Compress the image data for inclusion in the IDAT chunk
        compressed_data = zlib.compress(image_data)
        ihdr_data = b''.join([
            int.to_bytes(self.width, 4, 'big'),
            int.to_bytes(self.height, 4, 'big'),
            bytes([self.bit_depth, self.color_type, self.compress, self.filter, self.interlace])
        ])

        png_data = b''.join([
            b'\x89PNG\r\n\x1a\n',  # PNG signature
            int.to_bytes(13, 4, 'big'), b'IHDR', ihdr_data, zlib.crc32(b'IHDR' + ihdr_data).to_bytes(4, 'big'),
            int.to_bytes(len(compressed_data), 4, 'big'), b'IDAT', compressed_data,
            zlib.crc32(b'IDAT' + compressed_data).to_bytes(4, 'big'),
            b'\x00\x00\x00\x00IEND\xaeB`\x82'  # IEND chunk
        ])

        with open(file_name, 'wb') as file:
            file.write(png_data)
