// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:eva/app/app.dart';
import 'package:eva/core/enums/eva_mode.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('EVA login takes the operator to the control center', (
    tester,
  ) async {
    await tester.pumpWidget(const EvaApp());

    expect(find.text('EVA ROBOT COMPANION'), findsOneWidget);
    await tester.enterText(
      find.byKey(const ValueKey('emailField')),
      'admin@eva.local',
    );
    await tester.enterText(
      find.byKey(const ValueKey('passwordField')),
      'admin123',
    );
    await tester.tap(find.text('Login'));
    await tester.pumpAndSettle();

    expect(find.text('EVA Companion'), findsOneWidget);
    expect(find.text('INTERACTION MODE'), findsOneWidget);
    expect(find.text('Guest activity'), findsOneWidget);
    expect(find.text('Guest tasks tracked by EVA'), findsOneWidget);
    expect(find.text('Recent conversations with EVA'), findsOneWidget);
  });

  testWidgets('mode switch changes the active EVA operating mode', (
    tester,
  ) async {
    await tester.pumpWidget(const EvaApp());

    await tester.enterText(
      find.byKey(const ValueKey('emailField')),
      'admin@eva.local',
    );
    await tester.enterText(
      find.byKey(const ValueKey('passwordField')),
      'admin123',
    );
    await tester.tap(find.text('Login'));
    await tester.pumpAndSettle();

    final initial = tester.widget<SegmentedButton<EvaMode>>(
      find.byType(SegmentedButton<EvaMode>),
    );
    expect(initial.selected, {EvaMode.hospitality});

    await tester.tap(find.text('PLAY WITH EVA'));
    await tester.pumpAndSettle();

    final updated = tester.widget<SegmentedButton<EvaMode>>(
      find.byType(SegmentedButton<EvaMode>),
    );
    expect(updated.selected, {EvaMode.cognitive});
    expect(find.text('Play with EVA'), findsOneWidget);
    expect(find.text('20 Questions'), findsNWidgets(2));
    expect(find.text('Robot-reported task progress'), findsOneWidget);
    expect(find.text('Listen & Remember'), findsNWidgets(2));

    await tester.tap(find.text('Ask EVA').first);
    await tester.pumpAndSettle();

    expect(
      find.text('Demo: ask EVA to play 20 Questions by voice.'),
      findsOneWidget,
    );
    expect(find.textContaining('Moves:'), findsNothing);
  });
}
