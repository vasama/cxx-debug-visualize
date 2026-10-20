// A few toy data structures, standing in for a real library whose
// debugger visualizations are described in visualizers/.
#pragma once

#include <cstddef>
#include <cstring>
#include <new>
#include <utility>

namespace mylib {

struct Point {
  int x = 0;
  int y = 0;
};

class String {
public:
  String(const char *text) : Length(std::strlen(text)) {
    Data = new char[Length + 1];
    std::memcpy(Data, text, Length + 1);
  }
  ~String() { delete[] Data; }
  String(const String &) = delete;
  String &operator=(const String &) = delete;
  std::size_t size() const { return Length; }

private:
  char *Data;
  std::size_t Length;
};

template <typename T> class Vector {
public:
  Vector() = default;
  ~Vector() {
    for (std::size_t i = 0; i < Size; ++i)
      Begin[i].~T();
    ::operator delete(Begin);
  }
  Vector(const Vector &) = delete;
  Vector &operator=(const Vector &) = delete;

  void push_back(T value) {
    if (Size == Capacity)
      grow();
    new (&Begin[Size++]) T(std::move(value));
  }
  std::size_t size() const { return Size; }

private:
  void grow() {
    std::size_t newCapacity = Capacity ? Capacity * 2 : 4;
    T *newBegin = static_cast<T *>(::operator new(newCapacity * sizeof(T)));
    for (std::size_t i = 0; i < Size; ++i) {
      new (&newBegin[i]) T(std::move(Begin[i]));
      Begin[i].~T();
    }
    ::operator delete(Begin);
    Begin = newBegin;
    Capacity = newCapacity;
  }

  T *Begin = nullptr;
  std::size_t Size = 0;
  std::size_t Capacity = 0;
};

template <typename T> class Optional {
public:
  Optional() : HasValue(false) {}
  Optional(T value) : HasValue(true) { new (&Storage) T(std::move(value)); }
  ~Optional() {
    if (HasValue)
      reinterpret_cast<T *>(&Storage)->~T();
  }

private:
  alignas(T) unsigned char Storage[sizeof(T)];
  bool HasValue;
};

template <typename T> class List {
  struct Node {
    T Value;
    Node *Next;
  };

public:
  List() = default;
  ~List() {
    while (Head) {
      Node *next = Head->Next;
      delete Head;
      Head = next;
    }
  }
  List(const List &) = delete;
  List &operator=(const List &) = delete;

  void push_front(T value) {
    Head = new Node{std::move(value), Head};
    ++Count;
  }

private:
  Node *Head = nullptr;
  std::size_t Count = 0;
};

// Unbalanced binary search tree mapping int keys to values.
template <typename V> class IntMap {
  struct Node {
    int Key;
    V Value;
    Node *Left = nullptr;
    Node *Right = nullptr;
  };

public:
  IntMap() = default;
  ~IntMap() { destroy(Root); }
  IntMap(const IntMap &) = delete;
  IntMap &operator=(const IntMap &) = delete;

  void insert(int key, V value) {
    Node **slot = &Root;
    while (*slot) {
      if (key == (*slot)->Key) {
        (*slot)->Value = std::move(value);
        return;
      }
      slot = key < (*slot)->Key ? &(*slot)->Left : &(*slot)->Right;
    }
    *slot = new Node{key, std::move(value)};
    ++Count;
  }

private:
  static void destroy(Node *node) {
    if (!node)
      return;
    destroy(node->Left);
    destroy(node->Right);
    delete node;
  }

  Node *Root = nullptr;
  std::size_t Count = 0;
};

} // namespace mylib
