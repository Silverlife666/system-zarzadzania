import 'package:shared_preferences/shared_preferences.dart';
import 'inventory_models.dart';

class LocalStore {
  static const _recordsKey = 'inventory_records_v1';
  static const _operatorKey = 'inventory_operator_v1';
  static const _catalogKey = 'inventory_catalog_v1';
  final SharedPreferencesAsync _preferences = SharedPreferencesAsync();
  Future<List<InventoryRecord>> loadRecords() async => decodeRecords(await _preferences.getString(_recordsKey) ?? '[]');
  Future<void> saveRecords(List<InventoryRecord> records) => _preferences.setString(_recordsKey, encodeRecords(records));
  Future<String> loadOperator() => _preferences.getString(_operatorKey).then((value) => value ?? '');
  Future<void> saveOperator(String value) => _preferences.setString(_operatorKey, value.trim());
  Future<List<ProductCatalogItem>> loadCatalog() async => decodeCatalog(await _preferences.getString(_catalogKey) ?? '[]');
  Future<void> saveCatalog(List<ProductCatalogItem> items) => _preferences.setString(_catalogKey, encodeCatalog(items));
}
