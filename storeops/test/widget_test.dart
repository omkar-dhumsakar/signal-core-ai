import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Smoke test: verifies the Flutter test harness itself works.
/// Full widget tests that depend on platform channels (HTTP, file_picker)
/// should be run via integration_test with a real device or emulator.
void main() {
  testWidgets('Flutter test harness is functional', (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: Center(child: Text('Signal Core AI')),
        ),
      ),
    );
    expect(find.text('Signal Core AI'), findsOneWidget);
    expect(find.byType(Scaffold), findsOneWidget);
  });
}
