// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';

import 'package:emburn_inventory/inventory_models.dart';

void main() {
  test('normalizuje QR tacki do trwałego identyfikatora', () {
    expect(normalizeTray('TRAY|000145'), '000145');
    expect(trayPayload('000145'), 'TRAY|000145');
  });

  test('odczytuje pełne dane z nowej etykiety QR', () {
    final encoded = base64Url.encode(utf8.encode(jsonEncode({
      'product_name': 'Rolls Biały 12,5',
      'nominal_quantity': 667,
      'actual_quantity': 667,
      'operator': 'Ala',
    })));
    final data = trayQrData('TRAY|000001|$encoded');
    expect(data['tray_id'], '000001');
    expect(data['product_name'], 'Rolls Biały 12,5');
    expect(data['actual_quantity'], 667);
  });
}
