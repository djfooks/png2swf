import sys
import struct
import zlib
from glob import glob
import png

tag_code_map = {}
tag_code_map[0] = "end_of_file"
tag_code_map[1] = "show_frame"
tag_code_map[4] = "place_object"
tag_code_map[5] = "remove_object"
tag_code_map[9] = "set_background_color"
tag_code_map[14] = "define_sound"
tag_code_map[20] = "define_bits_lossless"
tag_code_map[21] = "define_bits_jpeg_2"
tag_code_map[26] = "place_object2"
tag_code_map[28] = "remove_object2"
tag_code_map[43] = "frame_label"
tag_code_map[35] = "define_bits_jpeg_3"
tag_code_map[36] = "define_bits_lossless_2"
tag_code_map[56] = "export_assets"
tag_code_map[65] = "script_limits"
tag_code_map[69] = "file_attributes"
tag_code_map[70] = "place_object3"
tag_code_map[76] = "symbol_class"
tag_code_map[77] = "metadata"
tag_code_map[78] = "define_scaling_grid"
tag_code_map[82] = "do_abc"
tag_code_map[86] = "define_scene_and_frame_label_data"

tag_str_map = {}
for (tag_id, tag_name) in tag_code_map.items():
	tag_str_map[tag_name] = tag_id

def zipstreams(filename):
	"""Return all zip streams and their positions in file."""
	with open(filename, 'rb') as fh:
		data = fh.read()
	i = 0
	while i < len(data):
		try:
			zo = zlib.decompressobj()
			yield i, zo.decompress(data[i:])
			i += len(data[i:]) - len(zo.unused_data)
		except zlib.error:
			i += 1

# https://formats.kaitai.io/swf/index.html
def main():
	print("Processing...")
	filename = sys.argv[1]

	print(filename)

	mode = "replace"

	with open(filename, "rb") as f:
		sig0 = f.read(1)
		sig1 = f.read(1)
		sig2 = f.read(1)

		print(sig0)

		if sig1 != "W" or sig2 != "S":
			print(sys.argv[1] + " is not a SWF file")
			return

		version = struct.unpack('<B', f.read(1))[0]
		print("File version " + str(version))

		file_length = struct.unpack('<L', f.read(4))[0]
		print("File length " + str(file_length))

		zo = zlib.decompressobj()
		internal_bytes = zo.decompress(f.read())
		print("Internal bytes " + str(len(internal_bytes)))

		rectangle_nbits = struct.unpack('<B', internal_bytes[0])[0] >> 3
		print("rectangle_nbits " + str(rectangle_nbits))

		rectangle_bytes = ((rectangle_nbits * 4 - 3) + 7) / 8
		print("rectangle_nbytes " + str(rectangle_bytes))

		index = rectangle_bytes + 1

		frame_rate = struct.unpack('<H', internal_bytes[index:index+2])[0]
		index = index + 2
		print("frame_rate " + str(frame_rate))

		frame_count = struct.unpack('<H', internal_bytes[index:index+2])[0]
		index = index + 2
		print("frame_count " + str(frame_count))

		def tag_parser(index, tag_info):
			tag_info["tag_start_index"] = index
			tag_code_and_length = struct.unpack('<H', internal_bytes[index:index+2])[0]
			index = index + 2
			tag_info["tag_code_and_length"] = tag_code_and_length

			tag_code = tag_code_and_length >> 6
			tag_info["tag_code"] = tag_code
			try:
				tag_info["tag_code_str"] = tag_code_map[tag_code]
			except KeyError:
				tag_info["tag_code_str"] = "unknown"

			small_len = tag_code_and_length & 0b111111
			tag_info["small_len"] = small_len

			if small_len == 0x3f:
				big_len = struct.unpack('<I', internal_bytes[index:index+4])[0]
				tag_info["big_len"] = big_len
				index = index + 4

				tag_info["data_index"] = index
				tag_info["len"] = big_len

				index = index + big_len
			else:
				tag_info["data_index"] = index
				tag_info["len"] = small_len
				index = index + small_len

			tag_info["data_end_index"] = tag_info["data_index"] + tag_info["len"]
			return index

		def update_tag(tag_info, new_tag_data):
			small_len = 0x3f
			if len(new_tag_data) < 0x3f:
				small_len = len(new_tag_data)

			tag_code_and_length = (tag_info["tag_code"] << 6) | small_len

			tag_header = ''
			tag_header = tag_header + struct.pack('<H', tag_code_and_length)

			if len(new_tag_data) >= 0x3f:
				tag_header = tag_header + struct.pack('<I', len(new_tag_data))

			print("len(new_tag_data) " + str(len(new_tag_data)))

			return internal_bytes[:tag_info["tag_start_index"]] + tag_header + new_tag_data + internal_bytes[tag_info["data_end_index"]:]


		tag_info = {}
		index = tag_parser(index, tag_info)
		print((tag_info["tag_code_str"], tag_info["len"]))

		has_symbol_class = False
		output_png = None

		while tag_info["tag_code"] != 0:
			tag_info = {}
			next_index = tag_parser(index, tag_info)
			print((tag_info["tag_code_str"], tag_info["len"]))

			if tag_info["tag_code_str"] == "symbol_class":
				has_symbol_class = True
				index = tag_info["data_index"]
				num_symbols = struct.unpack('<H', internal_bytes[index:index+2])[0]
				index = index + 2
				print("    num_symbols " + str(num_symbols))
				for i in xrange(num_symbols):
					symbol_tag = struct.unpack('<H', internal_bytes[index:index+2])[0]
					index = index + 2
					print("    " + str(i) + "::")
					print("        symbol_tag " + str(symbol_tag))

					name = ""
					name_start = index
					while internal_bytes[index] != '\x00':
						name = name + internal_bytes[index]
						index = index + 1
					print("        symbol_name " + name)

					if name == "Blue":
						internal_bytes = internal_bytes[:name_start] + 'X' + internal_bytes[name_start+1:]

			if tag_info["tag_code_str"] == "define_bits_lossless_2":

				index = tag_info["data_index"]

				character_id = struct.unpack('<H', internal_bytes[index:index+2])[0]
				index = index + 2
				print("    character_id " + str(character_id))

				bitmap_format = struct.unpack('<B', internal_bytes[index:index+1])[0]
				index = index + 1
				print("    bitmap_format " + str(bitmap_format))

				bitmap_width = struct.unpack('<H', internal_bytes[index:index+2])[0]
				index = index + 2
				print("    bitmap_width " + str(bitmap_width))

				bitmap_height = struct.unpack('<H', internal_bytes[index:index+2])[0]
				index = index + 2
				print("    bitmap_height " + str(bitmap_height))

				bitmap_zo = zlib.decompressobj()
				bitmap_internal_bytes = bitmap_zo.decompress(internal_bytes[index:])
				compressed_size = len(internal_bytes[index:]) - len(bitmap_zo.unused_data)
				print("    compressed_size RAW " + str(compressed_size))

				image_compressed_bytes = zlib.compress(bitmap_internal_bytes, -1)
				print("    compressed_size -1 " + str(len(image_compressed_bytes)))
				for i in xrange(10):
					image_compressed_bytes = zlib.compress(bitmap_internal_bytes, -1)
					print("    compressed_size " + str(i) + " " + str(len(image_compressed_bytes)))

				if mode == "replace":
					bitmap_start_index = index

					png_f = open('in.png', 'rb')
					input_png = png.Reader(png_f)
					(input_width, input_height, input_rows, input_info) = input_png.read()
					print("    input_width " + str(input_width))
					print("    input_height " + str(input_height))
					#print(input_info)
					if input_info['greyscale'] or not input_info['alpha']:
						print("Just use @:bitmap for simple RGB png files")
						return

					if bitmap_format != 5:
						print("Unknown bitmap format")
						return

					image_values = [0] * input_width * input_height * 4
					image_index = 0
					for input_row in input_rows:
						row_index = 0
						for x in xrange(input_width):
							pixel_R = input_row[row_index + 0]
							pixel_G = input_row[row_index + 1]
							pixel_B = input_row[row_index + 2]
							pixel_A = input_row[row_index + 3]
							#print("    " + str(image_index) + " pixel_RGBA " + str(pixel_R) + ", " + str(pixel_G) + ", " + str(pixel_B) + ", " + str(pixel_A))

							image_values[image_index + 0] = struct.pack('<B', pixel_A)
							image_values[image_index + 1] = struct.pack('<B', pixel_R)
							image_values[image_index + 2] = struct.pack('<B', pixel_G)
							image_values[image_index + 3] = struct.pack('<B', pixel_B)
							image_index = image_index + 4
							row_index = row_index + 4

					print('    bitmap_internal_bytes size ' + str(len(bitmap_internal_bytes) / 4))
					print('    input_internal_bytes size ' + str(input_width * input_height))

					image_str = ''.join(image_values)
					image_compressed_bytes = zlib.compress(image_str, 4)

					print('    image_compressed_bytes ' + str(len(image_compressed_bytes)))

					new_tag_data = ''
					new_tag_data = new_tag_data + struct.pack('<H', character_id)
					new_tag_data = new_tag_data + struct.pack('<B', bitmap_format)
					new_tag_data = new_tag_data + struct.pack('<H', bitmap_width)
					new_tag_data = new_tag_data + struct.pack('<H', bitmap_height)

					new_tag_data = new_tag_data + image_compressed_bytes
					internal_bytes = update_tag(tag_info, new_tag_data)

					## TODO update the file length

					index = tag_info["tag_start_index"]
					#index = tag_parser(index, tag_info)
					mode = "read"
					continue

				if mode == "read":
					print('    bitmap_internal_bytes size ' + str(len(bitmap_internal_bytes) / 4))
					print('    bitmap_internal_bytes size check ' + str(bitmap_width * bitmap_height))

					pixels = []
					pixel_row = [0] * bitmap_width * 4
					bitmap_index = 0
					for y in xrange(bitmap_height):
						row_index = 0
						for x in xrange(bitmap_width):
							pixel_A = struct.unpack('<B', bitmap_internal_bytes[bitmap_index:bitmap_index+1])[0]
							bitmap_index = bitmap_index + 1
							pixel_R = struct.unpack('<B', bitmap_internal_bytes[bitmap_index:bitmap_index+1])[0]
							bitmap_index = bitmap_index + 1
							pixel_G = struct.unpack('<B', bitmap_internal_bytes[bitmap_index:bitmap_index+1])[0]
							bitmap_index = bitmap_index + 1
							pixel_B = struct.unpack('<B', bitmap_internal_bytes[bitmap_index:bitmap_index+1])[0]
							bitmap_index = bitmap_index + 1
							#print("    " + str(i) + " pixel_RGBA " + str(pixel_R) + ", " + str(pixel_G) + ", " + str(pixel_B) + ", " + str(pixel_A))
							pixel_row[row_index + 0] = pixel_R
							pixel_row[row_index + 1] = pixel_G
							pixel_row[row_index + 2] = pixel_B
							pixel_row[row_index + 3] = pixel_A
							row_index = row_index + 4

						pixels.append(pixel_row)
						pixel_row = [0] * bitmap_width * 4

					output_png = png.from_array(pixels, mode="RGBA")
					png_f = open('out.png', 'wb')
					w = png.Writer(bitmap_width, bitmap_height, greyscale=False, alpha=True)
					w.write(png_f, pixels)
					png_f.close()

			if tag_info["tag_code_str"] == "do_abc":
				index = tag_info["data_index"]

				flags = struct.unpack('<I', internal_bytes[index:index+4])[0]
				index = index + 4
				print("    flags " + str(flags))

				name = ""
				name_start = index
				while internal_bytes[index] != '\x00':
					name = name + internal_bytes[index]
					index = index + 1
				print("    name " + name)

				while True:
					found_index = internal_bytes.find("Blue", index, tag_info["data_end_index"])
					if found_index == -1:
						break
					internal_bytes = internal_bytes[:found_index] + 'X' + internal_bytes[found_index+1:]

			if tag_info["tag_code_str"] == "define_bits_jpeg_2":
				index = tag_info["data_index"]

				character_id = struct.unpack('<H', internal_bytes[index:index+2])[0]
				index = index + 2
				print("    character_id " + str(character_id))

			if tag_info["tag_code_str"] == "define_bits_jpeg_3":
				index = tag_info["data_index"]

				character_id = struct.unpack('<H', internal_bytes[index:index+2])[0]
				index = index + 2
				print("    character_id " + str(character_id))

				alpha_data_offset = struct.unpack('<I', internal_bytes[index:index+4])[0]
				index = index + 4
				print("    alpha_data_offset " + str(alpha_data_offset))

			# if tag_info["tag_code_str"] == "show_frame":
			# 	if not has_symbol_class:
			# 		class_name = 'Example2'
			# 		tag_id = tag_str_map["symbol_class"]
			# 		tag_length = len(class_name) + 5

			# 		if tag_length >= 0x3f:
			# 			print("TODO support >=63 length symbol class")
			# 			return

			# 		tag_code_and_length = (tag_id << 6) | tag_length

			# 		num_symbols = 1
			# 		symbol_tag = 1

			# 		symbol_class_tag_str = ''
			# 		symbol_class_tag_str = symbol_class_tag_str + struct.pack('<H', tag_code_and_length)
			# 		symbol_class_tag_str = symbol_class_tag_str + struct.pack('<H', num_symbols)

			# 		symbol_class_tag_str = symbol_class_tag_str + struct.pack('<H', symbol_tag)
			# 		symbol_class_tag_str = symbol_class_tag_str + class_name + '\x00'

			# 		internal_bytes = internal_bytes[:index] + symbol_class_tag_str + internal_bytes[index:]
			# 		continue

			index = next_index

		output_compressed_bytes = zlib.compress(internal_bytes)
		f.seek(0)

		new_file_length = len(output_compressed_bytes) + 8
		print("new_file_length " + str(new_file_length))

		if filename != "assets.swf":
			with open("assets.swf", 'wb') as wf:
				# copy the top of the header
				wf.write(f.read(4))
				# but set a new length
				wf.write(struct.pack('<L', new_file_length))
				wf.write(output_compressed_bytes)

main()
