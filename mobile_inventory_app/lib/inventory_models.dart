import 'dart:convert';

class ProductCatalogItem {
  const ProductCatalogItem({required this.ean, required this.sku, required this.name, required this.defaultQuantity});
  final String ean;
  final String sku;
  final String name;
  final int defaultQuantity;

  Map<String, dynamic> toJson() => {'ean': ean, 'sku': sku, 'name': name, 'default_quantity': defaultQuantity};
  factory ProductCatalogItem.fromJson(Map<String, dynamic> value) => ProductCatalogItem(
        ean: digits(value['ean'] as String? ?? ''), sku: value['sku'] as String? ?? '', name: value['name'] as String? ?? '', defaultQuantity: integer(value['default_quantity']),
      );

  factory ProductCatalogItem.fromCsv(Map<String, String> row) => ProductCatalogItem(
        ean: digits(row['EAN'] ?? row['EAN/GTIN'] ?? ''),
        sku: row['SKU'] ?? '',
        name: row['Nazwa produktu'] ?? row['Produkt'] ?? '',
        defaultQuantity: integer(row['Ilość domyślna w tacce'] ?? row['Ilość nominalna']),
      );
}

class InventoryRecord {
  const InventoryRecord({required this.timestamp, required this.operator, required this.ean, required this.trayId, required this.productName, required this.actualQuantity, required this.nominalQuantity});
  final DateTime timestamp;
  final String operator;
  final String ean;
  final String trayId;
  final String productName;
  final int actualQuantity;
  final int nominalQuantity;
  int get difference => actualQuantity - nominalQuantity;

  Map<String, dynamic> toJson() => {'timestamp': timestamp.toIso8601String(), 'operator': operator, 'ean': ean, 'tray_id': trayId, 'product_name': productName, 'actual_quantity': actualQuantity, 'nominal_quantity': nominalQuantity};
  factory InventoryRecord.fromJson(Map<String, dynamic> value) => InventoryRecord(
        timestamp: DateTime.tryParse(value['timestamp'] as String? ?? '') ?? DateTime.now(), operator: value['operator'] as String? ?? '',
        ean: value['ean'] as String? ?? '', trayId: normalizeTray(value['tray_id'] as String? ?? ''), productName: value['product_name'] as String? ?? '',
        actualQuantity: integer(value['actual_quantity']), nominalQuantity: integer(value['nominal_quantity']),
      );
  List<String> toCsvRow() => [timestamp.toIso8601String(), operator, ean, trayId, productName, actualQuantity.toString(), nominalQuantity.toString(), difference.toString()];
}

String digits(String value) => value.replaceAll(RegExp(r'[^0-9]'), '');
Map<String, dynamic> trayQrData(String value) {
  final text = value.trim();
  final parts = text.split('|');
  if (parts.length >= 2 && parts.first.toUpperCase() == 'TRAY') {
    final data = <String, dynamic>{'tray_id': parts[1].trim().toUpperCase()};
    if (parts.length >= 3) {
      try {
        final encoded = base64Url.normalize(parts.sublist(2).join('|'));
        final decoded = jsonDecode(utf8.decode(base64Url.decode(encoded)));
        if (decoded is Map<String, dynamic>) data.addAll(decoded);
      } catch (_) {
        // Starsze etykiety zawierają wyłącznie identyfikator tacki.
      }
    }
    return data;
  }
  return {'tray_id': text.toUpperCase()};
}

String normalizeTray(String value) => (trayQrData(value)['tray_id'] ?? '').toString();
String trayPayload(String trayId) => 'TRAY|${normalizeTray(trayId)}';
int integer(Object? value) => int.tryParse((value ?? '').toString().replaceAll(',', '.').split('.').first) ?? 0;
String encodeRecords(List<InventoryRecord> records) => jsonEncode(records.map((record) => record.toJson()).toList());
List<InventoryRecord> decodeRecords(String value) { try { return (jsonDecode(value) as List<dynamic>).map((item) => InventoryRecord.fromJson(item as Map<String, dynamic>)).toList(); } catch (_) { return []; } }
String encodeCatalog(List<ProductCatalogItem> items) => jsonEncode(items.map((item) => item.toJson()).toList());
List<ProductCatalogItem> decodeCatalog(String value) { try { return (jsonDecode(value) as List<dynamic>).map((item) => ProductCatalogItem.fromJson(item as Map<String, dynamic>)).toList(); } catch (_) { return []; } }
