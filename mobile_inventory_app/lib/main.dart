import 'dart:convert';
import 'dart:io';

import 'package:cross_file/cross_file.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import 'inventory_models.dart';
import 'local_store.dart';
import 'scanner_page.dart';

void main() => runApp(const InventoryApp());

class InventoryApp extends StatelessWidget {
  const InventoryApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'EMBURN Inwentaryzacja',
        theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
        home: const InventoryHome(),
      );
}

class InventoryHome extends StatefulWidget {
  const InventoryHome({super.key});
  @override
  State<InventoryHome> createState() => _InventoryHomeState();
}

class _InventoryHomeState extends State<InventoryHome> {
  final _store = LocalStore();
  final _operator = TextEditingController();
  final _ean = TextEditingController();
  final _tray = TextEditingController();
  final _product = TextEditingController();
  final _nominal = TextEditingController(text: '0');
  final _actual = TextEditingController(text: '0');
  List<ProductCatalogItem> _catalog = [];
  List<InventoryRecord> _records = [];
  bool _loading = true;

  @override
  void initState() { super.initState(); _load(); }
  @override
  void dispose() { for (final controller in [_operator, _ean, _tray, _product, _nominal, _actual]) { controller.dispose(); } super.dispose(); }

  Future<void> _load() async {
    final result = await Future.wait([_store.loadRecords(), _store.loadCatalog(), _store.loadOperator()]);
    if (!mounted) return;
    setState(() { _records = result[0] as List<InventoryRecord>; _catalog = result[1] as List<ProductCatalogItem>; _operator.text = result[2] as String; _loading = false; });
  }

  ProductCatalogItem? get _matchedProduct {
    final code = digits(_ean.text);
    return _catalog.cast<ProductCatalogItem?>().firstWhere((item) => item!.ean == code, orElse: () => null);
  }

  void _applyProductFromEan() {
    final product = _matchedProduct;
    if (product == null) return;
    setState(() { _product.text = product.name; _nominal.text = product.defaultQuantity.toString(); _actual.text = product.defaultQuantity.toString(); });
  }

  Future<String?> _scan(String title) => Navigator.of(context).push<String>(MaterialPageRoute(builder: (_) => ScannerPage(title: title)));

  Future<void> _scanProduct() async { final value = await _scan('Skanuj EAN produktu'); if (value != null) { _ean.text = value; _applyProductFromEan(); setState(() {}); } }
  Future<void> _scanTray() async {
    final value = await _scan('Skanuj QR tacki');
    if (value == null) return;
    final data = trayQrData(value);
    setState(() {
      _tray.text = (data['tray_id'] ?? '').toString();
      if ((data['product_name'] ?? '').toString().trim().isNotEmpty) _product.text = data['product_name'].toString();
      if (data['nominal_quantity'] != null) _nominal.text = integer(data['nominal_quantity']).toString();
      if (data['actual_quantity'] != null) _actual.text = integer(data['actual_quantity']).toString();
      if (_operator.text.trim().isEmpty && (data['operator'] ?? '').toString().trim().isNotEmpty) _operator.text = data['operator'].toString();
    });
  }

  Future<void> _importCatalog() async {
    final result = await FilePicker.platform.pickFiles(type: FileType.custom, allowedExtensions: ['csv'], withData: true);
    if (result == null || result.files.single.bytes == null) return;
    final text = utf8.decode(result.files.single.bytes!, allowMalformed: true);
    final lines = text.split(RegExp(r'\r?\n')).where((line) => line.trim().isNotEmpty).toList();
    if (lines.length < 2) { _message('Katalog CSV nie zawiera pozycji.'); return; }
    final separator = lines.first.contains(';') ? ';' : ',';
    final headers = lines.first.split(separator).map((item) => item.trim()).toList();
    final items = <ProductCatalogItem>[];
    for (final line in lines.skip(1)) {
      final values = line.split(separator);
      final row = <String, String>{for (var index = 0; index < headers.length; index++) headers[index]: index < values.length ? values[index].trim() : ''};
      final item = ProductCatalogItem.fromCsv(row);
      if (item.ean.isNotEmpty && item.name.isNotEmpty) items.add(item);
    }
    await _store.saveCatalog(items);
    if (mounted) setState(() => _catalog = items);
    _message('Zaimportowano ${items.length} kodów EAN do telefonu.');
  }

  InventoryRecord? _draft() {
    final trayId = normalizeTray(_tray.text);
    if (trayId.isEmpty || _product.text.trim().isEmpty) return null;
    return InventoryRecord(timestamp: DateTime.now(), operator: _operator.text.trim(), ean: digits(_ean.text), trayId: trayId, productName: _product.text.trim(), actualQuantity: integer(_actual.text), nominalQuantity: integer(_nominal.text));
  }

  Future<void> _saveRecord({bool duplicateAccepted = false}) async {
    final draft = _draft();
    if (draft == null) { _message('Zeskanuj tackę i podaj nazwę produktu.'); return; }
    if (!duplicateAccepted && _records.any((record) => record.trayId == draft.trayId)) {
      final accepted = await showDialog<bool>(context: context, builder: (context) => AlertDialog(
        title: const Text('Duplikat tacki'), content: Text('Tacka ${draft.trayId} jest już w historii. Zapisać drugi wpis?'),
        actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Anuluj')), FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Zapisz mimo to'))],
      ));
      if (accepted == true) await _saveRecord(duplicateAccepted: true);
      return;
    }
    final updated = [draft, ..._records];
    await _store.saveRecords(updated);
    await _store.saveOperator(_operator.text);
    if (!mounted) return;
    setState(() { _records = updated; _ean.clear(); _tray.clear(); _product.clear(); _nominal.text = '0'; _actual.text = '0'; });
    _message('Zapisano tackę ${draft.trayId}: ${draft.productName}.');
  }

  Future<void> _exportCsv() async {
    final buffer = StringBuffer('data/czas;operator;EAN/GTIN;ID tacki;Nazwa produktu;ilość rzeczywista;ilość nominalna;różnica\n');
    for (final record in _records.reversed) { buffer.writeln(record.toCsvRow().map(_csv).join(';')); }
    final directory = await getApplicationDocumentsDirectory();
    final file = File('${directory.path}/inwentaryzacja_${DateTime.now().toIso8601String().replaceAll(':', '-')}.csv');
    await file.writeAsString('\uFEFF$buffer', encoding: utf8);
    await SharePlus.instance.share(ShareParams(files: [XFile(file.path)], title: 'Inwentaryzacja EMBURN'));
  }

  String _csv(String value) => value.contains(RegExp(r'[;"\n]')) ? '"${value.replaceAll('"', '""')}"' : value;
  void _message(String text) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    final product = _matchedProduct;
    final draft = _draft();
    return Scaffold(
      appBar: AppBar(title: const Text('EMBURN — Inwentaryzacja'), actions: [IconButton(onPressed: _importCatalog, icon: const Icon(Icons.upload_file), tooltip: 'Importuj katalog CSV'), IconButton(onPressed: _records.isEmpty ? null : _exportCsv, icon: const Icon(Icons.ios_share), tooltip: 'Eksportuj CSV')]),
      body: SafeArea(child: ListView(padding: const EdgeInsets.all(16), children: [
        TextField(controller: _operator, decoration: const InputDecoration(labelText: 'Operator')),
        const SizedBox(height: 12),
        Text('Katalog offline: ${_catalog.length} kodów EAN · Historia: ${_records.length} wpisów'),
        const Divider(height: 32),
        TextField(controller: _ean, keyboardType: TextInputType.number, onChanged: (_) { _applyProductFromEan(); setState(() {}); }, decoration: InputDecoration(labelText: 'EAN / GTIN produktu', suffixIcon: IconButton(onPressed: _scanProduct, icon: const Icon(Icons.qr_code_scanner)))),
        if (_ean.text.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 8), child: Text(product == null ? 'EAN nie ma w katalogu — wpisz produkt ręcznie.' : 'Rozpoznano: ${product.name}', style: TextStyle(color: product == null ? Colors.orange : Colors.green))),
        const SizedBox(height: 10),
        TextField(controller: _tray, onChanged: (_) => setState(() {}), decoration: InputDecoration(labelText: 'QR / ID tacki', hintText: 'TRAY|0001', suffixIcon: IconButton(onPressed: _scanTray, icon: const Icon(Icons.qr_code_scanner)))),
        const SizedBox(height: 10),
        TextField(controller: _product, onChanged: (_) => setState(() {}), decoration: const InputDecoration(labelText: 'Nazwa produktu')),
        Row(children: [Expanded(child: TextField(controller: _nominal, keyboardType: TextInputType.number, onChanged: (_) => setState(() {}), decoration: const InputDecoration(labelText: 'Ilość nominalna'))), const SizedBox(width: 12), Expanded(child: TextField(controller: _actual, keyboardType: TextInputType.number, onChanged: (_) => setState(() {}), decoration: const InputDecoration(labelText: 'Ilość rzeczywista')))]),
        const SizedBox(height: 16),
        Card(child: Padding(padding: const EdgeInsets.all(14), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [const Text('Podgląd przed zapisem', style: TextStyle(fontWeight: FontWeight.bold)), const SizedBox(height: 6), Text(draft == null ? 'Uzupełnij tackę i produkt.' : 'Tacka ${draft.trayId} → ${draft.productName} → ${draft.actualQuantity} szt. (różnica: ${draft.difference})')]))),
        const SizedBox(height: 10),
        FilledButton.icon(onPressed: _saveRecord, icon: const Icon(Icons.save), label: const Text('Zapisz wpis i skanuj następny')),
        const Divider(height: 32),
        const Text('Ostatnie wpisy', style: TextStyle(fontWeight: FontWeight.bold)),
        ..._records.take(10).map((record) => ListTile(title: Text('${record.trayId} · ${record.productName}'), subtitle: Text('${record.actualQuantity} szt. · różnica ${record.difference}'), trailing: IconButton(icon: const Icon(Icons.delete_outline), onPressed: () async { final updated = List<InventoryRecord>.from(_records)..remove(record); await _store.saveRecords(updated); if (mounted) setState(() => _records = updated); }))),
      ])),
    );
  }
}
