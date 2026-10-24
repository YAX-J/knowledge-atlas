#include "a.cpp"
#include "b.cpp"
extern void external_missing();
template <typename T> void run(Alpha a, T unknown, bool flag) {
  Alpha::unique();
  a.save();
  unknown.save();
  external_missing();
  auto selected = flag ? &Alpha::save : &Alpha::save;
  (a.*selected)();
}
