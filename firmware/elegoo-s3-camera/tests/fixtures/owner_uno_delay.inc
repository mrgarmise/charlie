extern void _delay(unsigned long ms)
{
  delay(ms / TimeCompensation);
  wdt_reset();
}
