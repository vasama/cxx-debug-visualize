// A few toy data structures, standing in for a real library whose
// debugger visualizations are described in visualizers/.
#pragma once

#include <cstddef>
#include <cstring>
#include <new>
#include <utility>

namespace mylib {

struct point
{
  int x = 0;
  int y = 0;
};

class string
{
  char* m_data;
  std::size_t m_length;

public:
  string(char const* text) : m_length(std::strlen(text))
  {
    m_data = new char[m_length + 1];
    std::memcpy(m_data, text, m_length + 1);
  }
  string(string const&) = delete;
  string& operator=(string const&) = delete;
  ~string()
  {
    delete[] m_data;
  }

  std::size_t size() const
  {
    return m_length;
  }
};

template<typename T>
class vector
{
  T* m_begin = nullptr;
  std::size_t m_size = 0;
  std::size_t m_capacity = 0;

public:
  vector() = default;
  vector(vector const&) = delete;
  vector& operator=(vector const&) = delete;
  ~vector()
  {
    for (std::size_t i = 0; i < m_size; ++i)
      m_begin[i].~T();
    ::operator delete(m_begin);
  }

  void push_back(T value)
  {
    if (m_size == m_capacity)
      grow();
    new (&m_begin[m_size++]) T(std::move(value));
  }
  std::size_t size() const
  {
    return m_size;
  }

private:
  void grow()
  {
    std::size_t new_capacity = m_capacity ? m_capacity * 2 : 4;
    T* new_begin = static_cast<T*>(::operator new(new_capacity * sizeof(T)));
    for (std::size_t i = 0; i < m_size; ++i)
    {
      new (&new_begin[i]) T(std::move(m_begin[i]));
      m_begin[i].~T();
    }
    ::operator delete(m_begin);
    m_begin = new_begin;
    m_capacity = new_capacity;
  }
};

template<typename T>
class optional
{
  alignas(T) unsigned char m_storage[sizeof(T)];
  bool m_has_value;

public:
  optional() : m_has_value(false)
  {
  }
  optional(T value) : m_has_value(true)
  {
    new (&m_storage) T(std::move(value));
  }
  ~optional()
  {
    if (m_has_value)
      reinterpret_cast<T*>(&m_storage)->~T();
  }
};

template<typename T>
class list
{
  struct node
  {
    T value;
    node* next;
  };

  node* m_head = nullptr;
  std::size_t m_count = 0;

public:
  list() = default;
  list(list const&) = delete;
  list& operator=(list const&) = delete;
  ~list()
  {
    while (m_head)
    {
      node* next = m_head->next;
      delete m_head;
      m_head = next;
    }
  }

  void push_front(T value)
  {
    m_head = new node{std::move(value), m_head};
    ++m_count;
  }
};

// Unbalanced binary search tree mapping int keys to values.
template<typename V>
class int_map
{
  struct node
  {
    int key;
    V value;
    node* left = nullptr;
    node* right = nullptr;
  };

  node* m_root = nullptr;
  std::size_t m_count = 0;

public:
  int_map() = default;
  int_map(int_map const&) = delete;
  int_map& operator=(int_map const&) = delete;
  ~int_map()
  {
    destroy(m_root);
  }

  void insert(int key, V value)
  {
    node** slot = &m_root;
    while (*slot)
    {
      if (key == (*slot)->key)
      {
        (*slot)->value = std::move(value);
        return;
      }
      slot = key < (*slot)->key ? &(*slot)->left : &(*slot)->right;
    }
    *slot = new node{key, std::move(value)};
    ++m_count;
  }

private:
  static void destroy(node* n)
  {
    if (!n)
      return;
    destroy(n->left);
    destroy(n->right);
    delete n;
  }
};

// Hash table with separate chaining, mapping int keys to values, with a fixed number of buckets.
// New keys go to the front of their bucket's chain.
template<typename V>
class hash_map
{
  struct node
  {
    int key;
    V value;
    node* next;
  };

  node** m_buckets;
  std::size_t m_bucket_count;
  std::size_t m_count = 0;

public:
  explicit hash_map(std::size_t bucket_count)
    : m_buckets(new node*[bucket_count]()), m_bucket_count(bucket_count)
  {
  }
  hash_map(hash_map const&) = delete;
  hash_map& operator=(hash_map const&) = delete;
  ~hash_map()
  {
    for (std::size_t i = 0; i < m_bucket_count; ++i)
    {
      while (node* n = m_buckets[i])
      {
        m_buckets[i] = n->next;
        delete n;
      }
    }
    delete[] m_buckets;
  }

  // `key` must not be negative.
  void insert(int key, V value)
  {
    node** bucket = &m_buckets[static_cast<std::size_t>(key) % m_bucket_count];
    for (node* n = *bucket; n; n = n->next)
    {
      if (n->key == key)
      {
        n->value = std::move(value);
        return;
      }
    }
    *bucket = new node{key, std::move(value), *bucket};
    ++m_count;
  }
};

// Fixed-capacity array of values that are each an integer, a real or nothing.
class variant_array
{
public:
  enum kind : unsigned char
  {
    none,
    integer,
    real
  };

private:
  struct entry
  {
    kind tag;
    union
    {
      int i;
      double d;
    };
  };

  entry* m_entries;
  std::size_t m_capacity;
  std::size_t m_size = 0;

public:
  explicit variant_array(std::size_t capacity)
    : m_entries(new entry[capacity]), m_capacity(capacity)
  {
  }
  variant_array(variant_array const&) = delete;
  variant_array& operator=(variant_array const&) = delete;
  ~variant_array()
  {
    delete[] m_entries;
  }

  // The array must not be full.
  void push_back(int value)
  {
    m_entries[m_size].tag = integer;
    m_entries[m_size++].i = value;
  }
  void push_back(double value)
  {
    m_entries[m_size].tag = real;
    m_entries[m_size++].d = value;
  }
  void push_back_none()
  {
    m_entries[m_size++].tag = none;
  }
};

} // namespace mylib
