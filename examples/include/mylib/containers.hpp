// A few toy data structures, standing in for a real library whose
// debugger visualizations are described in visualizers/.
#pragma once

#include <cstddef>
#include <cstring>
#include <new>
#include <utility>

namespace mylib {

struct point {
  int x = 0;
  int y = 0;
};

class string {
public:
  string(const char *text) : length_(std::strlen(text)) {
    data_ = new char[length_ + 1];
    std::memcpy(data_, text, length_ + 1);
  }
  ~string() { delete[] data_; }
  string(const string &) = delete;
  string &operator=(const string &) = delete;
  std::size_t size() const { return length_; }

private:
  char *data_;
  std::size_t length_;
};

template <typename T> class vector {
public:
  vector() = default;
  ~vector() {
    for (std::size_t i = 0; i < size_; ++i)
      begin_[i].~T();
    ::operator delete(begin_);
  }
  vector(const vector &) = delete;
  vector &operator=(const vector &) = delete;

  void push_back(T value) {
    if (size_ == capacity_)
      grow();
    new (&begin_[size_++]) T(std::move(value));
  }
  std::size_t size() const { return size_; }

private:
  void grow() {
    std::size_t new_capacity = capacity_ ? capacity_ * 2 : 4;
    T *new_begin = static_cast<T *>(::operator new(new_capacity * sizeof(T)));
    for (std::size_t i = 0; i < size_; ++i) {
      new (&new_begin[i]) T(std::move(begin_[i]));
      begin_[i].~T();
    }
    ::operator delete(begin_);
    begin_ = new_begin;
    capacity_ = new_capacity;
  }

  T *begin_ = nullptr;
  std::size_t size_ = 0;
  std::size_t capacity_ = 0;
};

template <typename T> class optional {
public:
  optional() : has_value_(false) {}
  optional(T value) : has_value_(true) { new (&storage_) T(std::move(value)); }
  ~optional() {
    if (has_value_)
      reinterpret_cast<T *>(&storage_)->~T();
  }

private:
  alignas(T) unsigned char storage_[sizeof(T)];
  bool has_value_;
};

template <typename T> class list {
  struct node {
    T value;
    node *next;
  };

public:
  list() = default;
  ~list() {
    while (head_) {
      node *next = head_->next;
      delete head_;
      head_ = next;
    }
  }
  list(const list &) = delete;
  list &operator=(const list &) = delete;

  void push_front(T value) {
    head_ = new node{std::move(value), head_};
    ++count_;
  }

private:
  node *head_ = nullptr;
  std::size_t count_ = 0;
};

// Unbalanced binary search tree mapping int keys to values.
template <typename V> class int_map {
  struct node {
    int key;
    V value;
    node *left = nullptr;
    node *right = nullptr;
  };

public:
  int_map() = default;
  ~int_map() { destroy(root_); }
  int_map(const int_map &) = delete;
  int_map &operator=(const int_map &) = delete;

  void insert(int key, V value) {
    node **slot = &root_;
    while (*slot) {
      if (key == (*slot)->key) {
        (*slot)->value = std::move(value);
        return;
      }
      slot = key < (*slot)->key ? &(*slot)->left : &(*slot)->right;
    }
    *slot = new node{key, std::move(value)};
    ++count_;
  }

private:
  static void destroy(node *n) {
    if (!n)
      return;
    destroy(n->left);
    destroy(n->right);
    delete n;
  }

  node *root_ = nullptr;
  std::size_t count_ = 0;
};

// Hash table with separate chaining, mapping int keys to values, with a fixed number of buckets.
// New keys go to the front of their bucket's chain.
template <typename V> class hash_map {
  struct node {
    int key;
    V value;
    node *next;
  };

public:
  explicit hash_map(std::size_t bucket_count)
      : buckets_(new node *[bucket_count]()), bucket_count_(bucket_count) {}
  ~hash_map() {
    for (std::size_t i = 0; i < bucket_count_; ++i) {
      while (node *n = buckets_[i]) {
        buckets_[i] = n->next;
        delete n;
      }
    }
    delete[] buckets_;
  }
  hash_map(const hash_map &) = delete;
  hash_map &operator=(const hash_map &) = delete;

  // `key` must not be negative.
  void insert(int key, V value) {
    node **bucket = &buckets_[static_cast<std::size_t>(key) % bucket_count_];
    for (node *n = *bucket; n; n = n->next) {
      if (n->key == key) {
        n->value = std::move(value);
        return;
      }
    }
    *bucket = new node{key, std::move(value), *bucket};
    ++count_;
  }

private:
  node **buckets_;
  std::size_t bucket_count_;
  std::size_t count_ = 0;
};

// Fixed-capacity array of values that are each an integer, a real or nothing.
class variant_array {
public:
  enum kind : unsigned char { none, integer, real };

  explicit variant_array(std::size_t capacity)
      : entries_(new entry[capacity]), capacity_(capacity) {}
  ~variant_array() { delete[] entries_; }
  variant_array(const variant_array &) = delete;
  variant_array &operator=(const variant_array &) = delete;

  // The array must not be full.
  void push_back(int value) {
    entries_[size_].tag = integer;
    entries_[size_++].i = value;
  }
  void push_back(double value) {
    entries_[size_].tag = real;
    entries_[size_++].d = value;
  }
  void push_back_none() { entries_[size_++].tag = none; }

private:
  struct entry {
    kind tag;
    union {
      int i;
      double d;
    };
  };

  entry *entries_;
  std::size_t capacity_;
  std::size_t size_ = 0;
};

} // namespace mylib
