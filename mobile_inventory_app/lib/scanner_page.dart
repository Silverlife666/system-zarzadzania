import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

class ScannerPage extends StatefulWidget {
  const ScannerPage({super.key, required this.title});
  final String title;
  @override
  State<ScannerPage> createState() => _ScannerPageState();
}

class _ScannerPageState extends State<ScannerPage> {
  bool _accepted = false;
  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text(widget.title)),
        body: MobileScanner(onDetect: (capture) {
          if (_accepted || capture.barcodes.isEmpty) return;
          final value = capture.barcodes.first.rawValue;
          if (value == null || value.trim().isEmpty) return;
          _accepted = true;
          Navigator.of(context).pop(value.trim());
        }),
      );
}
