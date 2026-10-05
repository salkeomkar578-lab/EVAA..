import 'package:eva/core/enums/eva_mode.dart';
import 'package:eva/core/models/eva_models.dart';
import 'package:eva/core/services/eva_app_state.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('EVA app state', () {
    test('switches between voice games and hospitality', () {
      final state = EvaAppState(seeded: false);
      expect(state.currentMode, EvaMode.hospitality);

      state.setMode(EvaMode.cognitive);
      expect(state.currentMode, EvaMode.cognitive);
      expect(state.commandHistory.first.payload, {
        'from': 'Hospitality',
        'to': 'Play with EVA',
      });
    });

    test('robot status reflects online hardware and connection state', () {
      final state = EvaAppState(seeded: false);
      final status = state.robotStatus;

      expect(status.robotOnline, isTrue);
      expect(status.raspberryPiConnected, isTrue);
      expect(status.networkConnected, isTrue);
      expect(status.cameraOnline, isTrue);
    });

    test('demo preference and robot controls update independently', () {
      final state = EvaAppState(seeded: false);

      state.setDemoMode(false);
      expect(state.demoMode, isFalse);
      expect(state.robotStatus.robotOnline, isTrue);
      expect(state.robotStatus.raspberryPiConnected, isTrue);

      state.setRobotOnline(false);
      state.updatePeripherals(voice: false, vision: false, motors: false);
      expect(state.robotStatus.robotOnline, isFalse);
      expect(state.robotStatus.microphoneOnline, isFalse);
      expect(state.robotStatus.speakerOnline, isFalse);
      expect(state.robotStatus.cameraOnline, isFalse);
      expect(state.robotStatus.motorsOnline, isFalse);
    });

    test('service requests can be created and completed', () {
      final state = EvaAppState(seeded: false);
      final request = ServiceRequest(
        id: 'req-1',
        title: 'Housekeeping',
        room: '204',
        status: RequestStatus.assigned,
      );

      state.addServiceRequest(request);
      expect(state.serviceRequests.length, 1);

      state.updateServiceRequestStatus('req-1', RequestStatus.completed);
      expect(state.serviceRequests.first.status, RequestStatus.completed);
    });

    test('reminders can be added and tracked', () {
      final state = EvaAppState(seeded: false);
      state.addReminder(
        Reminder(
          id: 'r-1',
          title: 'Breakfast',
          time: '09:00',
          completed: false,
        ),
      );

      expect(state.reminders.length, 1);
      expect(state.reminders.first.title, 'Breakfast');
    });

    test('command generation emits expected robot commands', () {
      final command = RobotCommand(
        type: RobotCommandType.navigateTo,
        payload: {'destination': 'Conference Hall'},
      );

      expect(command.type, RobotCommandType.navigateTo);
      expect(command.payload['destination'], 'Conference Hall');
    });
  });
}
