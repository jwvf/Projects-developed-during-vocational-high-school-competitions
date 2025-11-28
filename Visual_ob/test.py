from visual_barcode import BarcodeScanner


if __name__ == "__main__":
    IMAGE_PATH = r"D:\ZhengHuo\nbss\Visual_ob\glare_qrcode.jpg"
    scanner = BarcodeScanner(IMAGE_PATH)
    scanner.run()
