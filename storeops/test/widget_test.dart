import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:storeops/main.dart';

void main() {
  testWidgets('App renders without crashing', (WidgetTester tester) async {
    await tester.pumpWidget(const StoreOpsApp());
    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
