/*
  Control de acceso facial - Microcontrolador
  Computación Ubicua - UDLA

  Recibe por serial (9600 baudios):
    'G' -> LED VERDE encendido  -> "acceso correcto"
    'R' -> LED ROJO encendido   -> "acceso denegado"
    'O' -> ambos LEDs apagados

  Conexiones (Arduino Nano 33 IoT):
    D10 -> resistencia 220 ohm -> ánodo (+) LED VERDE    -> cátodo (-) a GND
    D9  -> resistencia 220 ohm -> ánodo (+) LED AMARILLO -> cátodo (-) a GND
    (el LED amarillo reemplaza al rojo como indicador de "acceso denegado")
*/

const int LED_VERDE = 10;
const int LED_ROJO  = 9;   // LED amarillo = acceso denegado

void setup() {
  Serial.begin(9600);
  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_ROJO, OUTPUT);

  // Prueba de LEDs al encender
  digitalWrite(LED_VERDE, HIGH); digitalWrite(LED_ROJO, HIGH);
  delay(500);
  digitalWrite(LED_VERDE, LOW);  digitalWrite(LED_ROJO, LOW);
}

void loop() {
  if (Serial.available() > 0) {
    char comando = Serial.read();

    switch (comando) {
      case 'G':
        digitalWrite(LED_VERDE, HIGH);
        digitalWrite(LED_ROJO, LOW);
        Serial.println("acceso correcto");
        break;

      case 'R':
        digitalWrite(LED_VERDE, LOW);
        digitalWrite(LED_ROJO, HIGH);
        Serial.println("acceso denegado");
        break;

      case 'O':
        digitalWrite(LED_VERDE, LOW);
        digitalWrite(LED_ROJO, LOW);
        Serial.println("leds apagados");
        break;
    }
  }
}
